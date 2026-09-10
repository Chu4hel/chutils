"""Модуль скрейпинга, автоматизации и утилиты антидетекта."""

import importlib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .camoufox import (
        CAMOUFOX_AVAILABLE as CAMOUFOX_AVAILABLE,
    )
    from .camoufox import (
        get_async_camoufox_class as get_async_camoufox_class,
    )
    from .camoufox import (
        launch_camoufox as launch_camoufox,
    )
    from .humanize.antidetect import (
        extract_clearance_cookies as extract_clearance_cookies,
    )
    from .profiles import (
        BrowserProfile as BrowserProfile,
    )
    from .profiles import (
        ProfileManager as ProfileManager,
    )
    from .proxy import (
        AsyncProxyTunnel as AsyncProxyTunnel,
    )
    from .proxy import (
        ChromeProxyExtension as ChromeProxyExtension,
    )
    from .proxy import (
        ProxyConfig as ProxyConfig,
    )
    from .proxy import (
        ProxyPool as ProxyPool,
    )
    from .proxy import (
        async_nodriver_proxy as async_nodriver_proxy,
    )
    from .proxy import (
        check_proxy as check_proxy,
    )
    from .proxy import (
        get_nodriver_proxy_args as get_nodriver_proxy_args,
    )
    from .proxy import (
        get_playwright_proxy as get_playwright_proxy,
    )
    from .proxy import (
        get_selenium_proxy as get_selenium_proxy,
    )
    from .proxy import (
        nodriver_proxy as nodriver_proxy,
    )
    from .proxy import (
        parse_proxy as parse_proxy,
    )
    from .testing import (
        LiveBrowserSession as LiveBrowserSession,
    )
    from .testing import (
        LocalTestServer as LocalTestServer,
    )
    from .testing import (
        MockNodriverTab as MockNodriverTab,
    )
    from .testing import (
        MockPlaywrightPage as MockPlaywrightPage,
    )
    from .testing import (
        MockSeleniumDriver as MockSeleniumDriver,
    )
    from .testing import (
        SnapshotRecorder as SnapshotRecorder,
    )
    from .testing import (
        assert_extraction_complete as assert_extraction_complete,
    )
    from .testing import (
        assert_schema_match as assert_schema_match,
    )
    from .testing import (
        assert_valid_price as assert_valid_price,
    )
    from .testing import (
        assert_valid_url as assert_valid_url,
    )
    from .testing import (
        use_html_snapshot as use_html_snapshot,
    )

_LAZY_MAPPING = {
    "AsyncProxyTunnel": (".proxy", "AsyncProxyTunnel"),
    "BrowserProfile": (".profiles", "BrowserProfile"),
    "CAMOUFOX_AVAILABLE": (".camoufox", "CAMOUFOX_AVAILABLE"),
    "ChromeProxyExtension": (".proxy", "ChromeProxyExtension"),
    "LiveBrowserSession": (".testing", "LiveBrowserSession"),
    "LocalTestServer": (".testing", "LocalTestServer"),
    "MockNodriverTab": (".testing", "MockNodriverTab"),
    "MockPlaywrightPage": (".testing", "MockPlaywrightPage"),
    "MockSeleniumDriver": (".testing", "MockSeleniumDriver"),
    "ProfileManager": (".profiles", "ProfileManager"),
    "ProxyConfig": (".proxy", "ProxyConfig"),
    "ProxyPool": (".proxy", "ProxyPool"),
    "SnapshotRecorder": (".testing", "SnapshotRecorder"),
    "assert_extraction_complete": (".testing", "assert_extraction_complete"),
    "assert_schema_match": (".testing", "assert_schema_match"),
    "assert_valid_price": (".testing", "assert_valid_price"),
    "assert_valid_url": (".testing", "assert_valid_url"),
    "async_nodriver_proxy": (".proxy", "async_nodriver_proxy"),
    "check_proxy": (".proxy", "check_proxy"),
    "extract_clearance_cookies": (".humanize.antidetect", "extract_clearance_cookies"),
    "get_async_camoufox_class": (".camoufox", "get_async_camoufox_class"),
    "get_nodriver_proxy_args": (".proxy", "get_nodriver_proxy_args"),
    "get_playwright_proxy": (".proxy", "get_playwright_proxy"),
    "get_selenium_proxy": (".proxy", "get_selenium_proxy"),
    "launch_camoufox": (".camoufox", "launch_camoufox"),
    "nodriver_proxy": (".proxy", "nodriver_proxy"),
    "parse_proxy": (".proxy", "parse_proxy"),
    "use_html_snapshot": (".testing", "use_html_snapshot"),
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
            "camoufox",
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
    "CAMOUFOX_AVAILABLE",
    "AsyncProxyTunnel",
    "BrowserProfile",
    "ChromeProxyExtension",
    "LiveBrowserSession",
    "LocalTestServer",
    "MockNodriverTab",
    "MockPlaywrightPage",
    "MockSeleniumDriver",
    "ProfileManager",
    "ProxyConfig",
    "ProxyPool",
    "SnapshotRecorder",
    "assert_extraction_complete",
    "assert_schema_match",
    "assert_valid_price",
    "assert_valid_url",
    "async_nodriver_proxy",
    "camoufox",
    "captcha",
    "check_proxy",
    "concurrency",
    "extract_clearance_cookies",
    "get_async_camoufox_class",
    "get_nodriver_proxy_args",
    "get_playwright_proxy",
    "get_selenium_proxy",
    "humanize",
    "launch_camoufox",
    "nodriver_proxy",
    "parse_proxy",
    "proxy",
    "testing",
    "use_html_snapshot",
]
