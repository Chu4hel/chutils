"""
Тесты для chutils.http.client (HttpClient и AsyncHttpClient на httpx).

Проверяет:
- HttpClient: синхронные GET/POST/PUT/DELETE/PATCH через httpx
- AsyncHttpClient: асинхронные запросы через httpx.AsyncClient
- Fallback на UrllibFallbackClient при отсутствии httpx
- Интеграцию с ResiliencePolicy
- Переиспользование сессий (контекстный менеджер)
- Маскирование заголовков в логах
- Единоразовое предупреждение при fallback
"""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from chutils.http.fallback import HttpResponse
from chutils.http.resilience import ResiliencePolicy


# ─── Вспомогательные фабрики ─────────────────────────────────────────────────


def _make_httpx_response(
        status_code: int = 200,
        content: bytes = b'{"ok": true}',
        url: str = "http://example.com/",
        headers: dict[str, str] | None = None,
) -> MagicMock:
    """Создаёт мок httpx.Response."""
    mock = MagicMock()
    mock.status_code = status_code
    mock.content = content
    mock.text = content.decode("utf-8")
    mock.headers = headers or {}
    mock.url = url
    mock.elapsed.total_seconds.return_value = 0.05
    return mock


# ─── HttpClient: импорт и инициализация ──────────────────────────────────────


def test_http_client_importable() -> None:
    """HttpClient импортируется из chutils.http."""
    from chutils.http import HttpClient
    assert HttpClient is not None


def test_http_client_defaults() -> None:
    """Проверяет значения по умолчанию HttpClient."""
    from chutils.http import HttpClient
    client = HttpClient()
    assert client.base_url == ""
    assert client.timeout == 30.0
    assert client.policy is None


def test_http_client_custom_init() -> None:
    """Проверяет кастомные параметры HttpClient."""
    from chutils.http import HttpClient
    policy = ResiliencePolicy(retries=1)
    client = HttpClient(
        base_url="https://api.example.com",
        default_headers={"X-App": "test"},
        timeout=5.0,
        policy=policy,
    )
    assert client.base_url == "https://api.example.com"
    assert client.timeout == 5.0
    assert client.policy is policy


# ─── HttpClient: GET через httpx (мок) ───────────────────────────────────────


def test_http_client_get_uses_httpx_when_available() -> None:
    """HttpClient использует httpx.Client при его наличии."""
    from chutils.http import HttpClient

    mock_response = _make_httpx_response(200, b'{"key": "value"}')

    mock_httpx_client = MagicMock()
    mock_httpx_client.request.return_value = mock_response
    mock_httpx_client.__enter__ = lambda s: s
    mock_httpx_client.__exit__ = MagicMock(return_value=False)

    with patch("chutils.http.client.HTTPX_AVAILABLE", True):
        with patch("chutils.http.client.httpx") as mock_httpx:
            mock_httpx.Client.return_value = mock_httpx_client
            client = HttpClient(base_url="http://example.com")
            resp = client.get("/data")

    assert resp.status_code == 200


def test_http_client_get_falls_back_to_urllib_when_httpx_missing() -> None:
    """HttpClient использует UrllibFallbackClient, если httpx недоступен."""
    from chutils.http import HttpClient

    mock_resp = HttpResponse(200, {}, b'{"fallback": true}', 0.01, "http://example.com/data")

    with patch("chutils.http.client.HTTPX_AVAILABLE", False):
        client = HttpClient()
        with patch.object(client._get_fallback_client(), "request", return_value=mock_resp) as mock_req:
            resp = client.get("http://example.com/data")

    # Клиент должен вернуть HttpResponse
    assert resp.status_code == 200


def test_http_client_fallback_warning_emitted_once(caplog: Any) -> None:
    """При fallback на urllib логируется единоразовое предупреждение."""
    import logging
    from chutils.http import HttpClient

    mock_resp = HttpResponse(200, {}, b"ok", 0.01, "http://example.com/")

    with patch("chutils.http.client.HTTPX_AVAILABLE", False):
        with patch("chutils.http.client._FALLBACK_WARNING_EMITTED", False):
            client = HttpClient()
            fallback = client._get_fallback_client()
            with patch.object(fallback, "request", return_value=mock_resp):
                with caplog.at_level(logging.WARNING):
                    client.get("http://example.com/")
                    client.get("http://example.com/")  # второй вызов — предупреждение не должно дублироваться

    # Предупреждение о fallback должно быть не более одного раза
    fallback_warnings = [r for r in caplog.records if "fallback" in r.message.lower() or "urllib" in r.message.lower()]
    assert len(fallback_warnings) <= 1


# ─── HttpClient: HTTP-методы ─────────────────────────────────────────────────


@pytest.mark.parametrize("method", ["get", "post", "put", "delete", "patch"])
def test_http_client_methods_available(method: str) -> None:
    """Все HTTP-методы доступны у HttpClient."""
    from chutils.http import HttpClient
    client = HttpClient()
    assert callable(getattr(client, method))


def test_http_client_post_with_json() -> None:
    """HttpClient.post() передаёт JSON-данные."""
    from chutils.http import HttpClient

    mock_response = _make_httpx_response(201, b'{"id": 1}')
    mock_httpx_client = MagicMock()
    mock_httpx_client.request.return_value = mock_response
    mock_httpx_client.__enter__ = lambda s: s
    mock_httpx_client.__exit__ = MagicMock(return_value=False)

    with patch("chutils.http.client.HTTPX_AVAILABLE", True):
        with patch("chutils.http.client.httpx") as mock_httpx:
            mock_httpx.Client.return_value = mock_httpx_client
            client = HttpClient()
            resp = client.post("http://example.com/items", json_data={"name": "test"})

    assert resp.status_code == 201
    call_kwargs = mock_httpx_client.request.call_args.kwargs
    assert call_kwargs.get("json") == {"name": "test"}


# ─── HttpClient: контекстный менеджер ────────────────────────────────────────


def test_http_client_context_manager() -> None:
    """HttpClient работает как контекстный менеджер (with)."""
    from chutils.http import HttpClient

    mock_response = _make_httpx_response()
    mock_httpx_client = MagicMock()
    mock_httpx_client.request.return_value = mock_response
    mock_httpx_client.__enter__ = lambda s: s
    mock_httpx_client.__exit__ = MagicMock(return_value=False)

    with patch("chutils.http.client.HTTPX_AVAILABLE", True):
        with patch("chutils.http.client.httpx") as mock_httpx:
            mock_httpx.Client.return_value = mock_httpx_client
            with HttpClient() as client:
                resp = client.get("http://example.com/")

    assert resp.status_code == 200


# ─── HttpClient: интеграция с ResiliencePolicy ───────────────────────────────


def test_http_client_applies_policy_on_request() -> None:
    """HttpClient делегирует вызов через ResiliencePolicy.apply_sync."""
    from chutils.http import HttpClient

    mock_response = _make_httpx_response()
    policy = ResiliencePolicy(retries=0)

    with patch("chutils.http.client.HTTPX_AVAILABLE", True):
        with patch("chutils.http.client.httpx") as mock_httpx:
            mock_client = MagicMock()
            mock_client.request.return_value = mock_response
            mock_client.__enter__ = lambda s: s
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_httpx.Client.return_value = mock_client

            with patch.object(policy, "apply_sync", wraps=policy.apply_sync) as mock_apply:
                client = HttpClient(policy=policy)
                client.get("http://example.com/")

    mock_apply.assert_called_once()


# ─── HttpClient: маскирование заголовков ─────────────────────────────────────


def test_http_client_masks_auth_in_logs(caplog: Any) -> None:
    """Authorization не появляется в логах в открытом виде."""
    import logging
    from chutils.http import HttpClient

    mock_response = _make_httpx_response()
    mock_httpx_client = MagicMock()
    mock_httpx_client.request.return_value = mock_response
    mock_httpx_client.__enter__ = lambda s: s
    mock_httpx_client.__exit__ = MagicMock(return_value=False)

    secret_token = "super-secret-bearer-token-12345"

    with patch("chutils.http.client.HTTPX_AVAILABLE", True):
        with patch("chutils.http.client.httpx") as mock_httpx:
            mock_httpx.Client.return_value = mock_httpx_client
            with caplog.at_level(logging.DEBUG):
                client = HttpClient(
                    default_headers={"Authorization": f"Bearer {secret_token}"}
                )
                client.get("http://example.com/")

    all_log_text = " ".join(r.message for r in caplog.records)
    assert secret_token not in all_log_text


# ─── AsyncHttpClient: импорт и инициализация ─────────────────────────────────


def test_async_http_client_importable() -> None:
    """AsyncHttpClient импортируется из chutils.http."""
    from chutils.http import AsyncHttpClient
    assert AsyncHttpClient is not None


def test_async_http_client_raises_without_httpx() -> None:
    """AsyncHttpClient вызывает OptionalDependencyError если httpx не установлен."""
    from chutils.exceptions import OptionalDependencyError
    from chutils.http import AsyncHttpClient

    with patch("chutils.http.client.HTTPX_AVAILABLE", False):
        with pytest.raises(OptionalDependencyError):
            AsyncHttpClient()


# ─── AsyncHttpClient: GET/POST ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_async_http_client_get() -> None:
    """AsyncHttpClient.get() выполняет async GET-запрос через httpx."""
    from chutils.http import AsyncHttpClient

    mock_response = _make_httpx_response(200, b'{"async": true}')

    mock_async_client = AsyncMock()
    mock_async_client.request = AsyncMock(return_value=mock_response)
    mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
    mock_async_client.__aexit__ = AsyncMock(return_value=False)

    with patch("chutils.http.client.HTTPX_AVAILABLE", True):
        with patch("chutils.http.client.httpx") as mock_httpx:
            mock_httpx.AsyncClient.return_value = mock_async_client
            async with AsyncHttpClient() as client:
                resp = await client.get("http://example.com/")

    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_async_http_client_post_with_json() -> None:
    """AsyncHttpClient.post() передаёт JSON."""
    from chutils.http import AsyncHttpClient

    mock_response = _make_httpx_response(201, b'{"id": 99}')
    mock_async_client = AsyncMock()
    mock_async_client.request = AsyncMock(return_value=mock_response)
    mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
    mock_async_client.__aexit__ = AsyncMock(return_value=False)

    with patch("chutils.http.client.HTTPX_AVAILABLE", True):
        with patch("chutils.http.client.httpx") as mock_httpx:
            mock_httpx.AsyncClient.return_value = mock_async_client
            async with AsyncHttpClient() as client:
                resp = await client.post(
                    "http://example.com/items", json_data={"title": "test"}
                )

    assert resp.status_code == 201
    call_kwargs = mock_async_client.request.call_args.kwargs
    assert call_kwargs.get("json") == {"title": "test"}


@pytest.mark.asyncio
async def test_async_http_client_applies_policy() -> None:
    """AsyncHttpClient делегирует вызов через ResiliencePolicy.apply_async."""
    from chutils.http import AsyncHttpClient

    mock_response = _make_httpx_response()
    policy = ResiliencePolicy(retries=0)

    mock_async_client = AsyncMock()
    mock_async_client.request = AsyncMock(return_value=mock_response)
    mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
    mock_async_client.__aexit__ = AsyncMock(return_value=False)

    with patch("chutils.http.client.HTTPX_AVAILABLE", True):
        with patch("chutils.http.client.httpx") as mock_httpx:
            mock_httpx.AsyncClient.return_value = mock_async_client
            with patch.object(policy, "apply_async", wraps=policy.apply_async) as mock_apply:
                async with AsyncHttpClient(policy=policy) as client:
                    await client.get("http://example.com/")

    mock_apply.assert_called_once()


@pytest.mark.asyncio
async def test_async_http_client_all_methods_available() -> None:
    """Все HTTP-методы доступны у AsyncHttpClient."""
    from chutils.http import AsyncHttpClient

    with patch("chutils.http.client.HTTPX_AVAILABLE", True):
        with patch("chutils.http.client.httpx"):
            client = AsyncHttpClient()

    for method in ("get", "post", "put", "delete", "patch"):
        assert callable(getattr(client, method))
