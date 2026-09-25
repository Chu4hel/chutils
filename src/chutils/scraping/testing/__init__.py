"""Модуль инструментов автотестирования скраперов и парсеров (chutils.scraping.testing)."""

import importlib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .assertions import (
        assert_extraction_complete as assert_extraction_complete,
    )
    from .assertions import (
        assert_schema_match as assert_schema_match,
    )
    from .assertions import (
        assert_valid_price as assert_valid_price,
    )
    from .assertions import (
        assert_valid_url as assert_valid_url,
    )
    from .mocks import (
        MockNodriverElement as MockNodriverElement,
    )
    from .mocks import (
        MockNodriverTab as MockNodriverTab,
    )
    from .mocks import (
        MockPlaywrightLocator as MockPlaywrightLocator,
    )
    from .mocks import (
        MockPlaywrightPage as MockPlaywrightPage,
    )
    from .mocks import (
        MockSeleniumDriver as MockSeleniumDriver,
    )
    from .mocks import (
        MockSeleniumElement as MockSeleniumElement,
    )
    from .server import (
        LocalTestServer as LocalTestServer,
    )
    from .server import (
        RecordedRequest as RecordedRequest,
    )
    from .server import (
        TestResponse as TestResponse,
    )
    from .session import (
        LiveBrowserSession as LiveBrowserSession,
    )
    from .dom_models import (
        DOMActionSessionReport as DOMActionSessionReport,
        DOMMutationDiff as DOMMutationDiff,
        RecordedAction as RecordedAction,
        RecordedChecklistItem as RecordedChecklistItem,
        ViewportInfo as ViewportInfo,
    )
    from .dom_scripts import (
        CORE_DOM_HELPERS_JS as CORE_DOM_HELPERS_JS,
        PAGE_META_SCRIPT as PAGE_META_SCRIPT,
        POLL_RECORDED_ACTIONS_SCRIPT as POLL_RECORDED_ACTIONS_SCRIPT,
        build_inject_recorder_hud_script as build_inject_recorder_hud_script,
        build_scan_selectors_script as build_scan_selectors_script,
        get_recorder_hud_ui_js as get_recorder_hud_ui_js,
    )
    from .recorder import (
        DOMActionRecorder as DOMActionRecorder,
        DOMActionRecorderHUD as DOMActionRecorderHUD,
    )
    from .snapshot import (
        SnapshotRecorder as SnapshotRecorder,
    )
    from .snapshot import (
        use_html_snapshot as use_html_snapshot,
    )

_LAZY_MAPPING = {
    "CORE_DOM_HELPERS_JS": (".dom_scripts", "CORE_DOM_HELPERS_JS"),
    "DOMActionRecorder": (".recorder", "DOMActionRecorder"),
    "DOMActionRecorderHUD": (".recorder", "DOMActionRecorderHUD"),
    "DOMActionSessionReport": (".dom_models", "DOMActionSessionReport"),
    "DOMMutationDiff": (".dom_models", "DOMMutationDiff"),
    "LiveBrowserSession": (".session", "LiveBrowserSession"),
    "LocalTestServer": (".server", "LocalTestServer"),
    "MockNodriverElement": (".mocks", "MockNodriverElement"),
    "MockNodriverTab": (".mocks", "MockNodriverTab"),
    "MockPlaywrightLocator": (".mocks", "MockPlaywrightLocator"),
    "MockPlaywrightPage": (".mocks", "MockPlaywrightPage"),
    "MockSeleniumDriver": (".mocks", "MockSeleniumDriver"),
    "MockSeleniumElement": (".mocks", "MockSeleniumElement"),
    "PAGE_META_SCRIPT": (".dom_scripts", "PAGE_META_SCRIPT"),
    "POLL_RECORDED_ACTIONS_SCRIPT": (".dom_scripts", "POLL_RECORDED_ACTIONS_SCRIPT"),
    "RecordedAction": (".dom_models", "RecordedAction"),
    "RecordedChecklistItem": (".dom_models", "RecordedChecklistItem"),
    "RecordedRequest": (".server", "RecordedRequest"),
    "SnapshotRecorder": (".snapshot", "SnapshotRecorder"),
    "TestResponse": (".server", "TestResponse"),
    "ViewportInfo": (".dom_models", "ViewportInfo"),
    "assert_extraction_complete": (".assertions", "assert_extraction_complete"),
    "assert_schema_match": (".assertions", "assert_schema_match"),
    "assert_valid_price": (".assertions", "assert_valid_price"),
    "assert_valid_url": (".assertions", "assert_valid_url"),
    "build_inject_recorder_hud_script": (".dom_scripts", "build_inject_recorder_hud_script"),
    "build_scan_selectors_script": (".dom_scripts", "build_scan_selectors_script"),
    "get_recorder_hud_ui_js": (".dom_scripts", "get_recorder_hud_ui_js"),
    "use_html_snapshot": (".snapshot", "use_html_snapshot"),
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
            "assertions",
            "dom_models",
            "dom_scripts",
            "fixtures",
            "mocks",
            "recorder",
            "server",
            "session",
            "snapshot",
            "__all__",
            "__doc__",
        ]
    )


__all__ = [
    "CORE_DOM_HELPERS_JS",
    "DOMActionRecorder",
    "DOMActionRecorderHUD",
    "DOMActionSessionReport",
    "DOMMutationDiff",
    "LiveBrowserSession",
    "LocalTestServer",
    "MockNodriverElement",
    "MockNodriverTab",
    "MockPlaywrightLocator",
    "MockPlaywrightPage",
    "MockSeleniumDriver",
    "MockSeleniumElement",
    "PAGE_META_SCRIPT",
    "POLL_RECORDED_ACTIONS_SCRIPT",
    "RecordedAction",
    "RecordedChecklistItem",
    "RecordedRequest",
    "SnapshotRecorder",
    "TestResponse",
    "ViewportInfo",
    "assert_extraction_complete",
    "assert_schema_match",
    "assert_valid_price",
    "assert_valid_url",
    "assertions",
    "build_inject_recorder_hud_script",
    "build_scan_selectors_script",
    "dom_models",
    "dom_scripts",
    "fixtures",
    "get_recorder_hud_ui_js",
    "mocks",
    "recorder",
    "server",
    "session",
    "snapshot",
    "use_html_snapshot",
]
