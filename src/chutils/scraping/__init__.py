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
    from .fingerprint import (
        FingerprintProfile as FingerprintProfile,
    )
    from .fingerprint import (
        FingerprintSynthesizer as FingerprintSynthesizer,
    )
    from .humanize.antidetect import (
        extract_clearance_cookies as extract_clearance_cookies,
    )
    from .humanize.behavior import (
        BehavioralProfile as BehavioralProfile,
    )
    from .humanize.config import (
        AntidetectConfig as AntidetectConfig,
    )
    from .humanize.turnstile import (
        detect_cf_turnstile as detect_cf_turnstile,
    )
    from .humanize.turnstile import (
        is_cf_turnstile_solved as is_cf_turnstile_solved,
    )
    from .humanize.turnstile import (
        solve_cf_turnstile as solve_cf_turnstile,
    )
    from .nodriver import (
        launch_nodriver as launch_nodriver,
    )
    from .nodriver import (
        nodriver_session as nodriver_session,
    )
    from .profiles import (
        BrowserProfile as BrowserProfile,
    )
    from .profiles import (
        ProfileManager as ProfileManager,
    )
    from .profiles import (
        sanitize_profile as sanitize_profile,
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
    "AntidetectConfig": (".humanize.config", "AntidetectConfig"),
    "AsyncProxyTunnel": (".proxy", "AsyncProxyTunnel"),
    "BehavioralProfile": (".humanize.behavior", "BehavioralProfile"),
    "BrowserProfile": (".profiles", "BrowserProfile"),
    "CAMOUFOX_AVAILABLE": (".camoufox", "CAMOUFOX_AVAILABLE"),
    "ChromeProxyExtension": (".proxy", "ChromeProxyExtension"),
    "FingerprintProfile": (".fingerprint", "FingerprintProfile"),
    "FingerprintSynthesizer": (".fingerprint", "FingerprintSynthesizer"),
    "LiveBrowserSession": (".testing", "LiveBrowserSession"),
    "LocalTestServer": (".testing", "LocalTestServer"),
    "MockNodriverTab": (".testing", "MockNodriverTab"),
    "MockPlaywrightPage": (".testing", "MockPlaywrightPage"),
    "MockSeleniumDriver": (".testing", "MockSeleniumDriver"),
    "ProfileManager": (".profiles", "ProfileManager"),
    "ProxyConfig": (".proxy", "ProxyConfig"),
    "ProxyPool": (".proxy", "ProxyPool"),
    "SnapshotRecorder": (".testing", "SnapshotRecorder"),
    "sanitize_profile": (".profiles", "sanitize_profile"),
    "assert_extraction_complete": (".testing", "assert_extraction_complete"),
    "assert_schema_match": (".testing", "assert_schema_match"),
    "assert_valid_price": (".testing", "assert_valid_price"),
    "assert_valid_url": (".testing", "assert_valid_url"),
    "async_nodriver_proxy": (".proxy", "async_nodriver_proxy"),
    "check_proxy": (".proxy", "check_proxy"),
    "detect_cf_turnstile": (".humanize.turnstile", "detect_cf_turnstile"),
    "extract_clearance_cookies": (".humanize.antidetect", "extract_clearance_cookies"),
    "get_async_camoufox_class": (".camoufox", "get_async_camoufox_class"),
    "get_nodriver_proxy_args": (".proxy", "get_nodriver_proxy_args"),
    "get_playwright_proxy": (".proxy", "get_playwright_proxy"),
    "get_selenium_proxy": (".proxy", "get_selenium_proxy"),
    "is_cf_turnstile_solved": (".humanize.turnstile", "is_cf_turnstile_solved"),
    "launch_camoufox": (".camoufox", "launch_camoufox"),
    "launch_nodriver": (".nodriver", "launch_nodriver"),
    "nodriver_proxy": (".proxy", "nodriver_proxy"),
    "nodriver_session": (".nodriver", "nodriver_session"),
    "parse_proxy": (".proxy", "parse_proxy"),
    "solve_cf_turnstile": (".humanize.turnstile", "solve_cf_turnstile"),
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
            "fingerprint",
            "humanize",
            "proxy",
            "testing",
            "__all__",
            "__doc__",
        ]
    )


__all__ = [
    "CAMOUFOX_AVAILABLE",
    "AntidetectConfig",
    "AsyncProxyTunnel",
    "BehavioralProfile",
    "BrowserProfile",
    "ChromeProxyExtension",
    "FingerprintProfile",
    "FingerprintSynthesizer",
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
    "detect_cf_turnstile",
    "extract_clearance_cookies",
    "fingerprint",
    "get_async_camoufox_class",
    "get_nodriver_proxy_args",
    "get_playwright_proxy",
    "get_selenium_proxy",
    "humanize",
    "is_cf_turnstile_solved",
    "launch_camoufox",
    "launch_nodriver",
    "nodriver_proxy",
    "nodriver_session",
    "parse_proxy",
    "proxy",
    "sanitize_profile",
    "solve_cf_turnstile",
    "testing",
    "use_html_snapshot",
]
