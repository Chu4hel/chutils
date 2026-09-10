"""Тесты адаптеров интеграции прокси с браузерными движками (nodriver, Playwright, Selenium)."""

from unittest.mock import MagicMock

import pytest

from chutils.scraping.proxy.adapters import (
    async_nodriver_proxy,
    get_nodriver_proxy_args,
    get_playwright_proxy,
    get_selenium_proxy,
    nodriver_proxy,
)
from chutils.scraping.proxy.models import ProxyConfig


def test_get_playwright_proxy() -> None:
    """Проверяет экспорт настроек для Playwright."""
    p_no_auth = ProxyConfig(host="1.2.3.4", port=8080, protocol="http")
    assert get_playwright_proxy(p_no_auth) == {"server": "http://1.2.3.4:8080"}

    p_auth = "socks5://user:pass@1.2.3.4:1080"
    assert get_playwright_proxy(p_auth) == {
        "server": "socks5://1.2.3.4:1080",
        "username": "user",
        "password": "pass",
    }


def test_get_selenium_proxy() -> None:
    """Проверяет экспорт настроек для Selenium."""
    p = "http://1.2.3.4:8080"
    # Без options
    res = get_selenium_proxy(p)
    assert res == {
        "proxyType": "MANUAL",
        "httpProxy": "1.2.3.4:8080",
        "sslProxy": "1.2.3.4:8080",
    }

    # С передачей mock Options
    mock_options = MagicMock()
    get_selenium_proxy(p, options=mock_options)
    mock_options.add_argument.assert_called_once_with("--proxy-server=http://1.2.3.4:8080")


def test_get_nodriver_proxy_args_no_auth() -> None:
    """Проверяет аргументы nodriver для прокси без авторизации."""
    args = get_nodriver_proxy_args("http://1.2.3.4:8080")
    assert args == ["--proxy-server=http://1.2.3.4:8080"]


def test_nodriver_proxy_sync_context() -> None:
    """Проверяет синхронный контекстный менеджер nodriver_proxy с авто-созданием расширения."""
    proxy = "http://user:pass@1.2.3.4:8080"
    with nodriver_proxy(proxy) as args:
        assert len(args) == 2
        assert any(a.startswith("--load-extension=") for a in args)
        assert any(a.startswith("--disable-extensions-except=") for a in args)


@pytest.mark.asyncio
async def test_nodriver_proxy_async_tunnel_context() -> None:
    """Проверяет асинхронный контекстный менеджер nodriver_proxy через локальный туннель."""
    proxy = "socks5://user:pass@127.0.0.1:9999"
    async with async_nodriver_proxy(proxy, mode="tunnel") as args:
        assert len(args) == 1
        assert args[0].startswith("--proxy-server=http://127.0.0.1:")
