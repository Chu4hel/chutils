"""Модуль управления прокси-серверами и аутентификацией."""

import importlib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .extension import ChromeProxyExtension as ChromeProxyExtension
    from .models import ProxyConfig as ProxyConfig
    from .models import ProxyHealthResult as ProxyHealthResult
    from .parser import parse_proxy as parse_proxy
    from .pool import ProxyPool as ProxyPool
    from .pool import check_proxy as check_proxy
    from .pool import check_proxy_async as check_proxy_async
    from .tunnel import AsyncProxyTunnel as AsyncProxyTunnel

_LAZY_MAPPING = {
    "AsyncProxyTunnel": (".tunnel", "AsyncProxyTunnel"),
    "ChromeProxyExtension": (".extension", "ChromeProxyExtension"),
    "ProxyConfig": (".models", "ProxyConfig"),
    "ProxyHealthResult": (".models", "ProxyHealthResult"),
    "ProxyPool": (".pool", "ProxyPool"),
    "check_proxy": (".pool", "check_proxy"),
    "check_proxy_async": (".pool", "check_proxy_async"),
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
    "ProxyConfig",
    "ProxyHealthResult",
    "ProxyPool",
    "check_proxy",
    "check_proxy_async",
    "parse_proxy",
]
