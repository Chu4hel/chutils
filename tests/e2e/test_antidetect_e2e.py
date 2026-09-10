"""E2E тесты для продвинутого антидетекта, сетевых TLS отпечатков и моста сессий."""

from __future__ import annotations

import os
import urllib.request
from unittest.mock import AsyncMock, MagicMock

import pytest

# Гарантируем, что запросы к локальным серверам не перенаправляются в системный прокси
os.environ["NO_PROXY"] = "127.0.0.1,localhost"

from chutils.http.tls_client import TLSAsyncClient, TLSSession
from chutils.scraping.humanize.antidetect import _get_antidetect_js
from chutils.scraping.testing.server import LocalTestServer


def _is_internet_available() -> bool:
    """Проверяет доступность внешней сети для E2E сетевых тестов."""
    try:
        req = urllib.request.Request(
            "https://tls.peet.ws/api/all",
            headers={"User-Agent": "Mozilla/5.0"},
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            return bool(resp.status == 200)
    except Exception:
        return False


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_tls_async_client_peet_ws_e2e() -> None:
    """E2E тест: TLSAsyncClient отправляет запрос к tls.peet.ws и верифицирует TLS-отпечаток."""
    if not _is_internet_available():
        pytest.skip("Внешняя сеть или tls.peet.ws недоступны для E2E теста")

    async with TLSAsyncClient(
        impersonate="chrome120",
        fallback_to_standard=True,
    ) as client:
        response = await client.get("https://tls.peet.ws/api/all", timeout=10.0)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        assert "ip" in data
        assert "http_version" in data

        # Если доступен curl_cffi, сервис возвращает подробный блок tls
        if "tls" in data and isinstance(data["tls"], dict):
            tls_info = data["tls"]
            assert "ja3" in tls_info or "ja4" in tls_info or "ciphers" in tls_info


@pytest.mark.e2e
def test_antidetect_worker_and_stack_cloaking_e2e() -> None:
    """E2E тест: сгенерированный JS-скрипт антидетекта содержит все уровни защиты воркеров и V8 стеков."""
    js = _get_antidetect_js(
        webgl_vendor="CustomVendor",
        webgl_renderer="CustomRenderer",
        hardware_concurrency=12,
        device_memory=16,
    )

    # 1. Проверяем перехват Worker и SharedWorker
    assert "OriginalWorker = window.Worker" in js
    assert "OriginalSharedWorker = window.SharedWorker" in js
    assert "workerPreamble" in js
    assert "navigator.webdriver" in js

    # 2. Проверяем изоляцию V8 Error stack traces в makeNative
    assert "Error.captureStackTrace" in js
    assert "makeNative" in js

    # 3. Проверяем подмену параметров "на лету"
    assert "CustomVendor" in js
    assert "CustomRenderer" in js
    assert "12" in js
    assert "16" in js


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_browser_to_tls_client_e2e_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    """Сквозной E2E тест: извлечение clearance cookies из браузерной сессии и авторизованный запрос через TLSAsyncClient."""
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")

    with LocalTestServer() as server:
        protected_url = server.serve_html(
            "/api/data",
            '{"status": "ok", "message": "Access granted with clearance token"}',
            content_type="application/json",
        )

        # 1. Моделируем браузерную сессию (Playwright Page), прошедшую проверку Cloudflare
        mock_context = MagicMock()
        mock_context.cookies = AsyncMock(
            return_value=[
                {
                    "name": "cf_clearance",
                    "value": "e2e_valid_clearance_token_xyz",
                    "domain": "127.0.0.1",
                },
                {
                    "name": "session_id",
                    "value": "e2e_session_999",
                    "domain": "127.0.0.1",
                },
            ]
        )
        mock_page = MagicMock()
        mock_page.context = mock_context
        mock_page.evaluate = AsyncMock(
            return_value="Mozilla/5.0 E2E-Antidetect-Browser"
        )

        # 2. Инициализируем TLSAsyncClient из браузерной сессии
        client = await TLSAsyncClient.from_browser_session(
            mock_page,
            impersonate="chrome120",
            fallback_to_standard=True,
        )

        assert client.impersonate == "chrome120"
        assert (
            client.default_headers.get("User-Agent")
            == "Mozilla/5.0 E2E-Antidetect-Browser"
        )
        assert (
            "cf_clearance=e2e_valid_clearance_token_xyz"
            in client.default_headers.get("Cookie", "")
        )

        # 3. Выполняем асинхронный HTTP-запрос к защищенному эндпоинту сервера
        async with client:
            resp = await client.get(protected_url)
            assert resp.status_code == 200
            data = resp.json()
            assert isinstance(data, dict)
            assert data.get("status") == "ok"

        # 4. Проверяем журнал запросов сервера
        assert len(server.requests_log) >= 1
        last_req = server.requests_log[-1]
        assert last_req.path == "/api/data"
        assert (
            last_req.headers.get("User-Agent") == "Mozilla/5.0 E2E-Antidetect-Browser"
        )
        cookie_header = last_req.headers.get("Cookie", "")
        assert "cf_clearance=e2e_valid_clearance_token_xyz" in cookie_header


@pytest.mark.e2e
def test_browser_to_tls_session_sync_e2e_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    """Сквозной E2E тест: извлечение clearance cookies из Selenium и авторизованный запрос через TLSSession."""
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")

    with LocalTestServer() as server:
        protected_url = server.serve_html(
            "/sync/data",
            '{"status": "ok", "source": "selenium_bridge"}',
            content_type="application/json",
        )

        # 1. Моделируем синхронный Selenium WebDriver
        mock_driver = MagicMock()
        del mock_driver.context
        mock_driver.get_cookies.return_value = [
            {"name": "cf_clearance", "value": "sync_e2e_cf_token_123"},
            {"name": "user_auth", "value": "auth_token_456"},
        ]
        mock_driver.execute_script.return_value = "Mozilla/5.0 E2E-SeleniumSync"

        # 2. Инициализируем синхронную TLSSession
        session = TLSSession.from_browser_session(
            mock_driver,
            impersonate="chrome120",
            fallback_to_standard=True,
        )

        assert session.impersonate == "chrome120"
        assert (
            session.default_headers.get("User-Agent") == "Mozilla/5.0 E2E-SeleniumSync"
        )
        assert "cf_clearance=sync_e2e_cf_token_123" in session.default_headers.get(
            "Cookie", ""
        )

        # 3. Выполняем синхронный запрос к серверу
        resp = session.get(protected_url)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)
        assert data.get("source") == "selenium_bridge"

        # 4. Проверяем заголовок на сервере
        last_req = server.requests_log[-1]
        assert last_req.path == "/sync/data"
        assert last_req.headers.get("User-Agent") == "Mozilla/5.0 E2E-SeleniumSync"
        assert "cf_clearance=sync_e2e_cf_token_123" in last_req.headers.get(
            "Cookie", ""
        )
