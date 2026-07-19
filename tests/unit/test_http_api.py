"""
Тесты для standalone API-функций chutils.http.

Проверяет:
- chutils.http.get(), post(), put(), delete(), patch()
- Функции создают временный HttpClient и выполняют запрос
- Функции принимают все стандартные параметры (headers, json_data, timeout, policy)
- Экспорт из chutils (ленивый импорт)
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from chutils.http.fallback import HttpResponse


# ─── Фабрика mock-ответа ─────────────────────────────────────────────────────


def _mock_resp(status: int = 200, body: bytes = b'{"ok": true}') -> HttpResponse:
    return HttpResponse(status, {}, body, 0.01, "http://example.com/")


# ─── Тесты standalone-функций ────────────────────────────────────────────────


def test_http_get_standalone() -> None:
    """chutils.http.get() возвращает HttpResponse."""
    import chutils.http as http

    resp = _mock_resp()
    with patch("chutils.http.api.HttpClient") as mock_cls:
        instance = MagicMock()
        instance.get.return_value = resp
        instance.__enter__ = lambda s: s
        instance.__exit__ = MagicMock(return_value=False)
        mock_cls.return_value = instance

        result = http.get("http://example.com/")

    assert result.status_code == 200
    instance.get.assert_called_once_with("http://example.com/", headers=None, timeout=None)


def test_http_post_standalone_with_json() -> None:
    """chutils.http.post() передаёт json_data."""
    import chutils.http as http

    resp = _mock_resp(201)
    with patch("chutils.http.api.HttpClient") as mock_cls:
        instance = MagicMock()
        instance.post.return_value = resp
        instance.__enter__ = lambda s: s
        instance.__exit__ = MagicMock(return_value=False)
        mock_cls.return_value = instance

        result = http.post("http://example.com/items", json_data={"name": "x"})

    assert result.status_code == 201
    instance.post.assert_called_once_with(
        "http://example.com/items",
        headers=None,
        json_data={"name": "x"},
        data=None,
        timeout=None,
    )


def test_http_put_standalone() -> None:
    """chutils.http.put() работает корректно."""
    import chutils.http as http

    resp = _mock_resp(200)
    with patch("chutils.http.api.HttpClient") as mock_cls:
        instance = MagicMock()
        instance.put.return_value = resp
        instance.__enter__ = lambda s: s
        instance.__exit__ = MagicMock(return_value=False)
        mock_cls.return_value = instance

        result = http.put("http://example.com/item/1", json_data={"name": "updated"})

    assert result.status_code == 200


def test_http_delete_standalone() -> None:
    """chutils.http.delete() работает корректно."""
    import chutils.http as http

    resp = _mock_resp(204, b"")
    with patch("chutils.http.api.HttpClient") as mock_cls:
        instance = MagicMock()
        instance.delete.return_value = resp
        instance.__enter__ = lambda s: s
        instance.__exit__ = MagicMock(return_value=False)
        mock_cls.return_value = instance

        result = http.delete("http://example.com/item/1")

    assert result.status_code == 204


def test_http_patch_standalone() -> None:
    """chutils.http.patch() работает корректно."""
    import chutils.http as http

    resp = _mock_resp(200)
    with patch("chutils.http.api.HttpClient") as mock_cls:
        instance = MagicMock()
        instance.patch.return_value = resp
        instance.__enter__ = lambda s: s
        instance.__exit__ = MagicMock(return_value=False)
        mock_cls.return_value = instance

        result = http.patch("http://example.com/item/1", json_data={"active": False})

    assert result.status_code == 200


def test_http_get_passes_headers() -> None:
    """Standalone get() передаёт кастомные заголовки."""
    import chutils.http as http

    resp = _mock_resp()
    with patch("chutils.http.api.HttpClient") as mock_cls:
        instance = MagicMock()
        instance.get.return_value = resp
        instance.__enter__ = lambda s: s
        instance.__exit__ = MagicMock(return_value=False)
        mock_cls.return_value = instance

        http.get("http://example.com/", headers={"X-Token": "abc"})

    instance.get.assert_called_once_with(
        "http://example.com/", headers={"X-Token": "abc"}, timeout=None
    )


def test_http_get_passes_timeout() -> None:
    """Standalone get() передаёт таймаут."""
    import chutils.http as http

    resp = _mock_resp()
    with patch("chutils.http.api.HttpClient") as mock_cls:
        instance = MagicMock()
        instance.get.return_value = resp
        instance.__enter__ = lambda s: s
        instance.__exit__ = MagicMock(return_value=False)
        mock_cls.return_value = instance

        http.get("http://example.com/", timeout=5.0)

    instance.get.assert_called_once_with(
        "http://example.com/", headers=None, timeout=5.0
    )


def test_http_get_passes_policy() -> None:
    """Standalone get() передаёт ResiliencePolicy в HttpClient."""
    import chutils.http as http
    from chutils.http import ResiliencePolicy

    resp = _mock_resp()
    policy = ResiliencePolicy(retries=1)

    with patch("chutils.http.api.HttpClient") as mock_cls:
        instance = MagicMock()
        instance.get.return_value = resp
        instance.__enter__ = lambda s: s
        instance.__exit__ = MagicMock(return_value=False)
        mock_cls.return_value = instance

        http.get("http://example.com/", policy=policy)

    # HttpClient должен быть создан с policy
    call_kwargs = mock_cls.call_args.kwargs
    assert call_kwargs.get("policy") is policy


# ─── Экспорт через chutils (ленивый импорт) ──────────────────────────────────


def test_chutils_http_module_importable() -> None:
    """chutils.http импортируется через ленивую загрузку."""
    import chutils
    http_mod = chutils.http
    assert http_mod is not None


def test_chutils_http_client_importable_from_chutils() -> None:
    """HttpClient доступен через chutils.HttpClient."""
    import chutils
    assert hasattr(chutils, "HttpClient") or True  # lazy — проверяем через __getattr__
    from chutils import HttpClient
    assert HttpClient is not None


def test_chutils_async_http_client_importable() -> None:
    """AsyncHttpClient доступен через chutils.AsyncHttpClient."""
    from chutils import AsyncHttpClient
    assert AsyncHttpClient is not None


def test_chutils_resilience_policy_importable() -> None:
    """ResiliencePolicy доступен через chutils.ResiliencePolicy."""
    from chutils import ResiliencePolicy
    assert ResiliencePolicy is not None


def test_chutils_http_response_importable() -> None:
    """HttpResponse доступен через chutils.HttpResponse."""
    from chutils import HttpResponse
    assert HttpResponse is not None
