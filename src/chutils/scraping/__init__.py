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
        async_nodriver_proxy as async_nodriver_proxy,
        check_proxy as check_proxy,
        get_nodriver_proxy_args as get_nodriver_proxy_args,
        get_playwright_proxy as get_playwright_proxy,
        get_selenium_proxy as get_selenium_proxy,
        nodriver_proxy as nodriver_proxy,
        parse_proxy as parse_proxy,
    )
    from .testing import (
        MockNodriverTab as MockNodriverTab,
        MockPlaywrightPage as MockPlaywrightPage,
        MockSeleniumDriver as MockSeleniumDriver,
    )

_LAZY_MAPPING = {
    "AsyncProxyTunnel": (".proxy", "AsyncProxyTunnel"),
    "BrowserProfile": (".profiles", "BrowserProfile"),
    "ChromeProxyExtension": (".proxy", "ChromeProxyExtension"),
    "MockNodriverTab": (".testing", "MockNodriverTab"),
    "MockPlaywrightPage": (".testing", "MockPlaywrightPage"),
    "MockSeleniumDriver": (".testing", "MockSeleniumDriver"),
    "ProfileManager": (".profiles", "ProfileManager"),
    "ProxyConfig": (".proxy", "ProxyConfig"),
    "ProxyPool": (".proxy", "ProxyPool"),
    "async_nodriver_proxy": (".proxy", "async_nodriver_proxy"),
    "check_proxy": (".proxy", "check_proxy"),
    "get_nodriver_proxy_args": (".proxy", "get_nodriver_proxy_args"),
    "get_playwright_proxy": (".proxy", "get_playwright_proxy"),
    "get_selenium_proxy": (".proxy", "get_selenium_proxy"),
    "nodriver_proxy": (".proxy", "nodriver_proxy"),
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
        + [
            "captcha",
            "concurrency",
            "humanize",
            "proxy",
            "testing",
            "__all__",
            "__doc__",
        ]
    )


__all__ = [
    "AsyncProxyTunnel",
    "BrowserProfile",
    "ChromeProxyExtension",
    "MockNodriverTab",
    "MockPlaywrightPage",
    "MockSeleniumDriver",
    "ProfileManager",
    "ProxyConfig",
    "ProxyPool",
    "async_nodriver_proxy",
    "captcha",
    "check_proxy",
    "concurrency",
    "get_nodriver_proxy_args",
    "get_playwright_proxy",
    "get_selenium_proxy",
    "humanize",
    "nodriver_proxy",
    "parse_proxy",
    "proxy",
    "testing",
]
