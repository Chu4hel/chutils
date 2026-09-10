"""Тесты для TLSAsyncClient и TLSSession (модуль chutils.http.tls_client)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from chutils.exceptions import OptionalDependencyError
from chutils.http.fallback import HttpResponse
from chutils.http.tls_client import TLSAsyncClient, TLSSession
from chutils.scraping.proxy.models import ProxyConfig
from chutils.scraping.proxy.pool import ProxyPool


def test_tls_session_raises_when_curl_cffi_missing():
    """TLSSession выбрасывает OptionalDependencyError если curl-cffi не установлен и fallback_to_standard=False."""
    with patch("chutils.http.tls_client.CURL_CFFI_AVAILABLE", False):
        with pytest.raises(OptionalDependencyError) as exc_info:
            TLSSession(impersonate="chrome120", fallback_to_standard=False)
        assert "curl-cffi" in str(exc_info.value)


@pytest.mark.asyncio
async def test_tls_async_client_raises_when_curl_cffi_missing():
    """TLSAsyncClient выбрасывает OptionalDependencyError если curl-cffi не установлен и fallback_to_standard=False."""
    with patch("chutils.http.tls_client.CURL_CFFI_AVAILABLE", False):
        with pytest.raises(OptionalDependencyError) as exc_info:
            TLSAsyncClient(impersonate="chrome120", fallback_to_standard=False)
        assert "curl-cffi" in str(exc_info.value)


def test_tls_session_fallback_to_standard():
    """TLSSession прозрачно использует стандартный клиент если curl-cffi отсутствует при fallback_to_standard=True."""
    with patch("chutils.http.tls_client.CURL_CFFI_AVAILABLE", False):
        client = TLSSession(impersonate="chrome120", fallback_to_standard=True)
        assert client.is_fallback is True
        assert client.impersonate == "chrome120"

        mock_resp = HttpResponse(
            status_code=200,
            headers={"content-type": "application/json"},
            content=b'{"status": "ok"}',
            elapsed=0.1,
            url="https://example.com",
        )
        with patch.object(
            client._standard_client, "request", return_value=mock_resp
        ) as mock_req:
            resp = client.get("https://example.com")
            assert resp.status_code == 200
            assert resp.json() == {"status": "ok"}
            mock_req.assert_called_once()


@pytest.mark.asyncio
async def test_tls_async_client_fallback_to_standard():
    """TLSAsyncClient прозрачно использует AsyncHttpClient если curl-cffi отсутствует при fallback_to_standard=True."""
    with patch("chutils.http.tls_client.CURL_CFFI_AVAILABLE", False):
        client = TLSAsyncClient(impersonate="safari17_0", fallback_to_standard=True)
        assert client.is_fallback is True
        assert client.impersonate == "safari17_0"

        mock_resp = HttpResponse(
            status_code=200,
            headers={"content-type": "application/json"},
            content=b'{"msg": "async_fallback"}',
            elapsed=0.05,
            url="https://example.com/api",
        )
        with patch.object(
            client._standard_client, "request", AsyncMock(return_value=mock_resp)
        ) as mock_req:
            resp = await client.get("https://example.com/api")
            assert resp.status_code == 200
            assert resp.text == '{"msg": "async_fallback"}'
            mock_req.assert_called_once()


def test_tls_session_with_mocked_curl_cffi():
    """TLSSession корректно проксирует запросы в curl_cffi Session."""
    mock_curl_resp = MagicMock()
    mock_curl_resp.status_code = 200
    mock_curl_resp.headers = {"server": "cloudflare"}
    mock_curl_resp.content = b"cloudflare passed"
    mock_curl_resp.url = "https://protected.com"
    mock_curl_resp.elapsed = 0.2

    mock_session_instance = MagicMock()
    mock_session_instance.request.return_value = mock_curl_resp

    with (
        patch("chutils.http.tls_client.CURL_CFFI_AVAILABLE", True),
        patch(
            "chutils.http.tls_client.create_curl_session",
            return_value=mock_session_instance,
        ),
    ):
        with TLSSession(impersonate="chrome120") as session:
            resp = session.get(
                "https://protected.com", headers={"User-Agent": "custom"}
            )
            assert resp.status_code == 200
            assert resp.text == "cloudflare passed"
            assert resp.headers["server"] == "cloudflare"
            mock_session_instance.request.assert_called_once_with(
                method="GET",
                url="https://protected.com",
                headers={"User-Agent": "custom"},
                timeout=30.0,
            )


@pytest.mark.asyncio
async def test_tls_async_client_with_mocked_curl_cffi():
    """TLSAsyncClient корректно выполняет асинхронные запросы через curl_cffi AsyncSession."""
    mock_curl_resp = MagicMock()
    mock_curl_resp.status_code = 201
    mock_curl_resp.headers = {"content-type": "application/json"}
    mock_curl_resp.content = b'{"created": true}'
    mock_curl_resp.url = "https://protected.com/items"
    mock_curl_resp.elapsed = 0.15

    mock_async_session = MagicMock()
    mock_async_session.request = AsyncMock(return_value=mock_curl_resp)
    mock_async_session.close = AsyncMock()

    with (
        patch("chutils.http.tls_client.CURL_CFFI_AVAILABLE", True),
        patch(
            "chutils.http.tls_client.create_curl_async_session",
            return_value=mock_async_session,
        ),
    ):
        async with TLSAsyncClient(impersonate="chrome131") as client:
            resp = await client.post("https://protected.com/items", json={"key": "val"})
            assert resp.status_code == 201
            assert resp.json() == {"created": True}
            mock_async_session.request.assert_called_once_with(
                method="POST",
                url="https://protected.com/items",
                json={"key": "val"},
                timeout=30.0,
            )


@pytest.mark.asyncio
async def test_tls_client_proxy_integration():
    """TLSAsyncClient автоматически применяет настройки прокси и ротации из ProxyPool."""
    p1 = ProxyConfig(
        protocol="http", host="10.0.0.1", port=8080, username="user", password="pass"
    )
    pool = ProxyPool([p1])

    mock_async_session = MagicMock()
    mock_curl_resp = MagicMock()
    mock_curl_resp.status_code = 200
    mock_curl_resp.headers = {}
    mock_curl_resp.content = b"proxied"
    mock_curl_resp.url = "https://api.ipify.org"
    mock_curl_resp.elapsed = 0.1
    mock_async_session.request = AsyncMock(return_value=mock_curl_resp)
    mock_async_session.close = AsyncMock()

    with (
        patch("chutils.http.tls_client.CURL_CFFI_AVAILABLE", True),
        patch(
            "chutils.http.tls_client.create_curl_async_session",
            return_value=mock_async_session,
        ) as mock_create,
    ):
        async with TLSAsyncClient(impersonate="chrome120", proxy_pool=pool) as client:
            resp = await client.get("https://api.ipify.org")
            assert resp.status_code == 200
            mock_create.assert_called_once()
            _, kwargs = mock_create.call_args
            assert kwargs["proxy"] == p1.url


@pytest.mark.asyncio
async def test_tls_client_proxy_tunnel_integration():
    """TLSAsyncClient успешно работает с локальным туннелем аутентификации AsyncProxyTunnel."""
    from chutils.scraping.proxy.tunnel import AsyncProxyTunnel

    upstream_proxy = ProxyConfig(
        protocol="http", host="proxy.example.com", port=8000, username="u", password="p"
    )
    tunnel = AsyncProxyTunnel(upstream_proxy, local_host="127.0.0.1", local_port=0)

    mock_async_session = MagicMock()
    mock_curl_resp = MagicMock()
    mock_curl_resp.status_code = 200
    mock_curl_resp.content = b"tunnel-ok"
    mock_curl_resp.headers = {}
    mock_curl_resp.elapsed = 0.05
    mock_curl_resp.url = "https://target.com"
    mock_async_session.request = AsyncMock(return_value=mock_curl_resp)
    mock_async_session.close = AsyncMock()

    with (
        patch("chutils.http.tls_client.CURL_CFFI_AVAILABLE", True),
        patch(
            "chutils.http.tls_client.create_curl_async_session",
            return_value=mock_async_session,
        ) as mock_create,
    ):
        async with tunnel:
            async with TLSAsyncClient(
                impersonate="chrome120", proxy=tunnel.local_url
            ) as client:
                resp = await client.get("https://target.com")
                assert resp.status_code == 200
                assert resp.text == "tunnel-ok"
                mock_create.assert_called_once()
                _, kwargs = mock_create.call_args
                assert kwargs["proxy"] == tunnel.local_url
