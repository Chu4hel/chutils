"""Модуль управления прокси-серверами и аутентификацией."""

import importlib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .adapters import async_nodriver_proxy as async_nodriver_proxy
    from .adapters import get_nodriver_proxy_args as get_nodriver_proxy_args
    from .adapters import get_playwright_proxy as get_playwright_proxy
    from .adapters import get_selenium_proxy as get_selenium_proxy
    from .adapters import nodriver_proxy as nodriver_proxy
    from .extension import ChromeProxyExtension as ChromeProxyExtension
    from .models import ProxyConfig as ProxyConfig
    from .models import ProxyHealthResult as ProxyHealthResult
    from .parser import parse_proxy as parse_proxy
    from .pool import ProxyPool as ProxyPool
    from .pool import check_proxy as check_proxy
    from .pool import check_proxy_async as check_proxy_async
    from .cache import FileCacheBackend as FileCacheBackend
    from .resolver import ProxyCandidate as ProxyCandidate
    from .resolver import SmartProxyResolver as SmartProxyResolver
    from .tunnel import AsyncProxyTunnel as AsyncProxyTunnel

_LAZY_MAPPING = {
    "AsyncProxyTunnel": (".tunnel", "AsyncProxyTunnel"),
    "ChromeProxyExtension": (".extension", "ChromeProxyExtension"),
    "FileCacheBackend": (".cache", "FileCacheBackend"),
    "ProxyCandidate": (".resolver", "ProxyCandidate"),
    "ProxyConfig": (".models", "ProxyConfig"),
    "ProxyHealthResult": (".models", "ProxyHealthResult"),
    "ProxyPool": (".pool", "ProxyPool"),
    "SmartProxyResolver": (".resolver", "SmartProxyResolver"),
    "async_nodriver_proxy": (".adapters", "async_nodriver_proxy"),
    "check_proxy": (".pool", "check_proxy"),
    "check_proxy_async": (".pool", "check_proxy_async"),
    "get_nodriver_proxy_args": (".adapters", "get_nodriver_proxy_args"),
    "get_playwright_proxy": (".adapters", "get_playwright_proxy"),
    "get_selenium_proxy": (".adapters", "get_selenium_proxy"),
    "nodriver_proxy": (".adapters", "nodriver_proxy"),
    "parse_proxy": (".parser", "parse_proxy"),
}


def __getattr__(name: str) -> Any:
    if name in _LAZY_MAPPING:
        mod_path, attr_name = _LAZY_MAPPING[name]
        module = importlib.import_module(mod_path, __name__)
        return getattr(module, attr_name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(list(_LAZY_MAPPING.keys()) + ["__all__", "__doc__"])


__all__ = [
    "AsyncProxyTunnel",
    "ChromeProxyExtension",
    "FileCacheBackend",
    "ProxyCandidate",
    "ProxyConfig",
    "ProxyHealthResult",
    "ProxyPool",
    "SmartProxyResolver",
    "async_nodriver_proxy",
    "check_proxy",
    "check_proxy_async",
    "get_nodriver_proxy_args",
    "get_playwright_proxy",
    "get_selenium_proxy",
    "nodriver_proxy",
    "parse_proxy",
]
