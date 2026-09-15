"""Тесты локального тестового HTTP-сервера и менеджера живых браузерных сессий."""

import asyncio
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from chutils.scraping.testing.server import LocalTestServer
from chutils.scraping.testing.session import LiveBrowserSession


def test_local_test_server_sync_routes() -> None:
    """Проверяет запуск сервера, отдачу HTML и логирование запросов."""
    with LocalTestServer() as server:
        assert server.port > 0

        # Регистрируем HTML маршрут
        html_url = server.serve_html("/page1", "<h1>Hello Scraping</h1>")
        assert html_url == f"http://127.0.0.1:{server.port}/page1"

        # Запрашиваем страницу через server.fetch (обходит системные прокси)
        resp = server.fetch("/page1", headers={"User-Agent": "TestBot/1.0"})
        assert resp.status == 200
        assert resp.text == "<h1>Hello Scraping</h1>"

        # Проверяем запись в лог запросов
        assert len(server.requests_log) == 1
        last_req = server.requests_log[0]
        assert last_req.path == "/page1"
        assert last_req.method == "GET"
        assert last_req.headers.get("User-Agent") == "TestBot/1.0"

        # Проверяем отдачу JSON
        json_url = server.serve_json("/api/products", [{"id": 1, "name": "Phone"}])
        resp_json = server.fetch(json_url)
        assert resp_json.status == 200
        assert resp_json.json() == [{"id": 1, "name": "Phone"}]

        # Проверяем 404
        resp_404 = server.fetch("/nonexistent")
        assert resp_404.status == 404
        assert "404 Not Found" in resp_404.text


@pytest.mark.asyncio
async def test_local_test_server_async_context() -> None:
    """Проверяет запуск сервера в асинхронном контекстном менеджере."""
    async with LocalTestServer() as server:
        assert server.is_running
        server.serve_html("/", "Index")
        url = server.url_for("/")

        # Выполняем HTTP запрос через fetch в потоке
        resp = await asyncio.to_thread(server.fetch, url)
        assert resp.status == 200
        assert resp.text == "Index"

    assert not server.is_running


def test_live_browser_session_cleanup() -> None:
    """Проверяет создание временного профиля, отслеживание процесса и гарантированный teardown."""
    session = LiveBrowserSession(browser_name="chromium")
    profile_dir: Path
    with session as s:
        profile_dir = s.user_data_dir
        assert profile_dir.exists()
        assert s.is_active

        # Эмулируем PID фиктивного процесса
        mock_process = MagicMock()
        mock_process.pid = 999999
        mock_process.is_running.return_value = False
        s.track_process(mock_process)

    # После выхода из контекстного менеджера профиль удален
    assert not profile_dir.exists()
    assert not session.is_active


def test_live_browser_session_zombie_kill() -> None:
    """Проверяет принудительное завершение зависшего процесса браузера (Kill Zombie)."""
    session = LiveBrowserSession()
    mock_proc = MagicMock()
    mock_proc.pid = 12345
    # Процесс еще активен
    mock_proc.is_running.side_effect = [True, False]

    session.track_process(mock_proc)
    session.cleanup()

    # Проверяем, что был вызван terminate / kill
    assert mock_proc.terminate.called or mock_proc.kill.called
