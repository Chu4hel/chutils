"""
Тесты для модуля chutils.http.fallback (UrllibFallbackClient).

Проверяет:
- Синхронные GET/POST запросы
- Передачу заголовков (включая дефолтные)
- Маскирование чувствительных заголовков в логах
- JSON-тело запроса и JSON-ответ
- Обработку HTTP-ошибок (4xx/5xx)
- Сетевые ошибки (URLError)
- Таймауты
- Интеграцию с ResiliencePolicy (retry при ошибке)
- Контекстный менеджер
"""
from __future__ import annotations

import io
import json
import urllib.error
import urllib.request
from http.client import HTTPMessage
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from chutils.http.fallback import HttpResponse, UrllibFallbackClient
from chutils.http.resilience import ResiliencePolicy


# ─── Вспомогательные фабрики ─────────────────────────────────────────────────


def _make_mock_response(
        status: int = 200,
        body: bytes = b"ok",
        url: str = "http://example.com",
        headers: dict[str, str] | None = None,
) -> MagicMock:
    """Создаёт мок urllib-ответа для использования в urlopen."""
    msg = HTTPMessage()
    for k, v in (headers or {}).items():
        msg[k] = v

    mock_resp = MagicMock()
    mock_resp.status = status
    mock_resp.url = url
    mock_resp.headers = msg
    mock_resp.read.return_value = body
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


def _make_http_error(
        code: int,
        body: bytes = b"error body",
        url: str = "http://example.com",
) -> urllib.error.HTTPError:
    """Создаёт HTTPError для тестирования обработки ошибок."""
    msg = HTTPMessage()
    fp = io.BytesIO(body)
    return urllib.error.HTTPError(url, code, f"HTTP {code}", msg, fp)  # type: ignore[arg-type]


# ─── HttpResponse ─────────────────────────────────────────────────────────────


def test_http_response_text() -> None:
    """HttpResponse.text декодирует тело в UTF-8."""
    resp = HttpResponse(200, {}, b"hello world", 0.1, "http://example.com")
    assert resp.text == "hello world"


def test_http_response_json() -> None:
    """HttpResponse.json() парсит JSON-тело."""
    body = json.dumps({"key": "value"}).encode()
    resp = HttpResponse(200, {}, body, 0.1, "http://example.com")
    assert resp.json() == {"key": "value"}


def test_http_response_raise_for_status_ok() -> None:
    """raise_for_status не вызывает исключение для 2xx."""
    resp = HttpResponse(200, {}, b"", 0.1, "http://example.com")
    resp.raise_for_status()  # Не должно выбросить


def test_http_response_raise_for_status_4xx() -> None:
    """raise_for_status вызывает HttpClientError для 4xx."""
    from chutils.exceptions import HttpClientError

    resp = HttpResponse(404, {}, b"not found", 0.1, "http://example.com/missing")
    with pytest.raises(HttpClientError, match="404"):
        resp.raise_for_status()


def test_http_response_raise_for_status_5xx() -> None:
    """raise_for_status вызывает HttpClientError для 5xx."""
    from chutils.exceptions import HttpClientError

    resp = HttpResponse(500, {}, b"server error", 0.1, "http://example.com")
    with pytest.raises(HttpClientError, match="500"):
        resp.raise_for_status()


# ─── UrllibFallbackClient: инициализация ─────────────────────────────────────


def test_client_defaults() -> None:
    """Проверяет значения по умолчанию клиента."""
    client = UrllibFallbackClient()
    assert client.base_url == ""
    assert client.default_headers == {}
    assert client.timeout == 30.0
    assert client.policy is None


def test_client_custom_init() -> None:
    """Проверяет кастомные значения при инициализации."""
    policy = ResiliencePolicy(retries=1)
    client = UrllibFallbackClient(
        base_url="https://api.example.com",
        default_headers={"X-App": "test"},
        timeout=5.0,
        policy=policy,
    )
    assert client.base_url == "https://api.example.com"
    assert client.default_headers == {"X-App": "test"}
    assert client.timeout == 5.0
    assert client.policy is policy


# ─── UrllibFallbackClient: URL-построение ────────────────────────────────────


def test_build_url_with_base() -> None:
    """_build_url добавляет base_url как префикс."""
    client = UrllibFallbackClient(base_url="https://api.example.com")
    assert client._build_url("/users/1") == "https://api.example.com/users/1"


def test_build_url_absolute_passthrough() -> None:
    """_build_url не изменяет абсолютные URL."""
    client = UrllibFallbackClient(base_url="https://api.example.com")
    assert client._build_url("https://other.com/path") == "https://other.com/path"


def test_build_url_no_base() -> None:
    """_build_url возвращает path как есть, если base_url не задан."""
    client = UrllibFallbackClient()
    assert client._build_url("https://example.com/path") == "https://example.com/path"


# ─── UrllibFallbackClient: GET ───────────────────────────────────────────────


def test_get_success() -> None:
    """GET-запрос возвращает корректный HttpResponse."""
    mock_resp = _make_mock_response(200, b'{"status": "ok"}', "http://example.com/data")

    with patch("urllib.request.urlopen", return_value=mock_resp) as mock_open:
        client = UrllibFallbackClient()
        resp = client.get("http://example.com/data")

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
    assert resp.url == "http://example.com/data"
    mock_open.assert_called_once()


def test_get_with_default_headers() -> None:
    """GET-запрос включает заголовки по умолчанию."""
    mock_resp = _make_mock_response()

    with patch("urllib.request.urlopen", return_value=mock_resp):
        with patch("urllib.request.Request") as mock_req_cls:
            mock_req_cls.return_value = MagicMock()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)

            client = UrllibFallbackClient(
                default_headers={"X-Custom": "value", "Authorization": "Bearer token"}
            )
            client.get("http://example.com/")

    call_kwargs: dict[str, Any] = mock_req_cls.call_args.kwargs
    headers = call_kwargs.get("headers", {})
    assert headers.get("X-Custom") == "value"
    assert headers.get("Authorization") == "Bearer token"


def test_get_merges_extra_headers() -> None:
    """GET-запрос объединяет дефолтные и переданные заголовки."""
    mock_resp = _make_mock_response()

    with patch("urllib.request.urlopen", return_value=mock_resp):
        with patch("urllib.request.Request") as mock_req_cls:
            mock_req_cls.return_value = MagicMock()

            client = UrllibFallbackClient(default_headers={"X-Default": "d"})
            client.get("http://example.com/", headers={"X-Extra": "e"})

    headers = mock_req_cls.call_args.kwargs.get("headers", {})
    assert headers.get("X-Default") == "d"
    assert headers.get("X-Extra") == "e"


# ─── UrllibFallbackClient: POST / JSON ───────────────────────────────────────


def test_post_with_json_data() -> None:
    """POST-запрос сериализует json_data и устанавливает Content-Type."""
    mock_resp = _make_mock_response(201, b'{"id": 42}')

    with patch("urllib.request.urlopen", return_value=mock_resp):
        with patch("urllib.request.Request") as mock_req_cls:
            mock_req_cls.return_value = MagicMock()

            client = UrllibFallbackClient()
            resp = client.post("http://example.com/items", json_data={"name": "test"})

    call_kwargs = mock_req_cls.call_args.kwargs
    body: bytes = call_kwargs.get("data", b"")
    headers = call_kwargs.get("headers", {})

    assert json.loads(body) == {"name": "test"}
    assert headers.get("Content-Type") == "application/json"


def test_post_with_raw_bytes() -> None:
    """POST-запрос отправляет сырые байты."""
    mock_resp = _make_mock_response(200, b"ok")

    with patch("urllib.request.urlopen", return_value=mock_resp):
        with patch("urllib.request.Request") as mock_req_cls:
            mock_req_cls.return_value = MagicMock()

            client = UrllibFallbackClient()
            client.post("http://example.com/upload", data=b"raw binary")

    body = mock_req_cls.call_args.kwargs.get("data")
    assert body == b"raw binary"


def test_post_raises_on_json_and_data_together() -> None:
    """POST-запрос вызывает ValueError при передаче json_data и data одновременно."""
    client = UrllibFallbackClient()
    with pytest.raises(ValueError, match="одновременно"):
        client.post("http://example.com/", json_data={"k": "v"}, data=b"raw")


# ─── UrllibFallbackClient: HTTP-ошибки ───────────────────────────────────────


def test_get_returns_response_on_http_error() -> None:
    """При HTTPError возвращается HttpResponse с соответствующим статус-кодом."""
    err = _make_http_error(404, b"not found", "http://example.com/missing")

    with patch("urllib.request.urlopen", side_effect=err):
        client = UrllibFallbackClient()
        resp = client.get("http://example.com/missing")

    assert resp.status_code == 404
    assert resp.content == b"not found"


def test_get_raises_on_url_error() -> None:
    """При URLError вызывается HttpClientError."""
    from chutils.exceptions import HttpClientError

    url_err = urllib.error.URLError("connection refused")

    with patch("urllib.request.urlopen", side_effect=url_err):
        client = UrllibFallbackClient()
        with pytest.raises(HttpClientError, match="Сетевая ошибка"):
            client.get("http://example.com/")


# ─── UrllibFallbackClient: таймаут ───────────────────────────────────────────


def test_request_uses_custom_timeout() -> None:
    """Таймаут передаётся в urlopen."""
    mock_resp = _make_mock_response()

    with patch("urllib.request.urlopen", return_value=mock_resp) as mock_open:
        client = UrllibFallbackClient(timeout=7.5)
        client.get("http://example.com/")

    _, call_kwargs = mock_open.call_args
    assert call_kwargs.get("timeout") == 7.5


def test_request_per_call_timeout_overrides_default() -> None:
    """Таймаут на уровне вызова переопределяет дефолтный."""
    mock_resp = _make_mock_response()

    with patch("urllib.request.urlopen", return_value=mock_resp) as mock_open:
        client = UrllibFallbackClient(timeout=30.0)
        client.get("http://example.com/", timeout=2.0)

    _, call_kwargs = mock_open.call_args
    assert call_kwargs.get("timeout") == 2.0


# ─── UrllibFallbackClient: маскирование заголовков ───────────────────────────


def test_mask_headers_hides_authorization() -> None:
    """Метод _mask маскирует Authorization."""
    client = UrllibFallbackClient()
    result = client._mask({"Authorization": "Bearer secret", "X-Custom": "visible"})
    assert result["Authorization"] == "[MASKED]"
    assert result["X-Custom"] == "visible"


def test_mask_headers_hides_cookie() -> None:
    """Метод _mask маскирует Cookie и Set-Cookie."""
    client = UrllibFallbackClient()
    result = client._mask({"cookie": "session=abc", "Set-Cookie": "id=xyz"})
    assert result["cookie"] == "[MASKED]"
    assert result["Set-Cookie"] == "[MASKED]"


def test_mask_headers_hides_custom_sensitive() -> None:
    """Кастомные сенситивные заголовки маскируются."""
    client = UrllibFallbackClient(sensitive_headers={"X-Internal-Secret"})
    result = client._mask({"X-Internal-Secret": "topsecret", "Content-Type": "application/json"})
    assert result["X-Internal-Secret"] == "[MASKED]"
    assert result["Content-Type"] == "application/json"


# ─── UrllibFallbackClient: резилиенс-интеграция ──────────────────────────────


def test_request_with_policy_retry_on_network_error() -> None:
    """Политика retry повторяет при сетевой ошибке."""
    from chutils.exceptions import HttpClientError

    call_count = 0

    def side_effect(*args: object, **kwargs: object) -> MagicMock:
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise urllib.error.URLError("timeout")
        return _make_mock_response(200, b"ok")

    policy = ResiliencePolicy(retries=3, retry_delay=0.0, retry_exceptions=(HttpClientError,))

    with patch("urllib.request.urlopen", side_effect=side_effect):
        client = UrllibFallbackClient(policy=policy)
        resp = client.get("http://example.com/")

    assert resp.status_code == 200
    assert call_count == 3


# ─── UrllibFallbackClient: HTTP-методы ───────────────────────────────────────


@pytest.mark.parametrize("method_name,http_method", [
    ("get", "GET"),
    ("delete", "DELETE"),
])
def test_simple_methods(method_name: str, http_method: str) -> None:
    """GET и DELETE правильно устанавливают HTTP-метод."""
    mock_resp = _make_mock_response()

    with patch("urllib.request.urlopen", return_value=mock_resp):
        with patch("urllib.request.Request") as mock_req_cls:
            mock_req_cls.return_value = MagicMock()
            client = UrllibFallbackClient()
            getattr(client, method_name)("http://example.com/")

    assert mock_req_cls.call_args.kwargs.get("method") == http_method


@pytest.mark.parametrize("method_name,http_method", [
    ("put", "PUT"),
    ("patch", "PATCH"),
])
def test_body_methods(method_name: str, http_method: str) -> None:
    """PUT и PATCH правильно устанавливают HTTP-метод."""
    mock_resp = _make_mock_response()

    with patch("urllib.request.urlopen", return_value=mock_resp):
        with patch("urllib.request.Request") as mock_req_cls:
            mock_req_cls.return_value = MagicMock()
            client = UrllibFallbackClient()
            getattr(client, method_name)("http://example.com/", json_data={"k": "v"})

    assert mock_req_cls.call_args.kwargs.get("method") == http_method


# ─── UrllibFallbackClient: контекстный менеджер ──────────────────────────────


def test_context_manager() -> None:
    """Клиент работает как контекстный менеджер."""
    mock_resp = _make_mock_response()

    with patch("urllib.request.urlopen", return_value=mock_resp):
        with UrllibFallbackClient() as client:
            resp = client.get("http://example.com/")

    assert resp.status_code == 200
