"""Модуль скрейпинга, автоматизации и утилиты антидетекта."""

import importlib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .profiles import (
        BrowserProfile as BrowserProfile,
    )
    from .profiles import (
        ProfileManager as ProfileManager,
    )
    from .proxy import (
        AsyncProxyTunnel as AsyncProxyTunnel,
        ChromeProxyExtension as ChromeProxyExtension,
        ProxyConfig as ProxyConfig,
        ProxyPool as ProxyPool,
        check_proxy as check_proxy,
        parse_proxy as parse_proxy,
    )

_LAZY_MAPPING = {
    "AsyncProxyTunnel": (".proxy", "AsyncProxyTunnel"),
    "BrowserProfile": (".profiles", "BrowserProfile"),
    "ChromeProxyExtension": (".proxy", "ChromeProxyExtension"),
    "ProfileManager": (".profiles", "ProfileManager"),
    "ProxyConfig": (".proxy", "ProxyConfig"),
    "ProxyPool": (".proxy", "ProxyPool"),
    "check_proxy": (".proxy", "check_proxy"),
    "parse_proxy": (".proxy", "parse_proxy"),
}


def __getattr__(name: str) -> Any:
    if name in _LAZY_MAPPING:
        mod_path, attr_name = _LAZY_MAPPING[name]
        module = importlib.import_module(mod_path, __name__)
        return getattr(module, attr_name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(
        list(_LAZY_MAPPING.keys())
        + ["captcha", "concurrency", "humanize", "proxy", "__all__", "__doc__"]
    )


__all__ = [
    "AsyncProxyTunnel",
    "BrowserProfile",
    "ChromeProxyExtension",
    "ProfileManager",
    "ProxyConfig",
    "ProxyPool",
    "captcha",
    "check_proxy",
    "concurrency",
    "humanize",
    "parse_proxy",
    "proxy",
]
