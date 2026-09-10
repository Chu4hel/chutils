"""Модуль инструментов автотестирования скраперов и парсеров (chutils.scraping.testing)."""

import importlib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .mocks import (
        MockNodriverElement as MockNodriverElement,
        MockNodriverTab as MockNodriverTab,
        MockPlaywrightLocator as MockPlaywrightLocator,
        MockPlaywrightPage as MockPlaywrightPage,
        MockSeleniumDriver as MockSeleniumDriver,
        MockSeleniumElement as MockSeleniumElement,
    )
    from .server import (
        LocalTestServer as LocalTestServer,
        RecordedRequest as RecordedRequest,
        TestResponse as TestResponse,
    )
    from .session import (
        LiveBrowserSession as LiveBrowserSession,
    )
    from .snapshot import (
        SnapshotRecorder as SnapshotRecorder,
        use_html_snapshot as use_html_snapshot,
    )

_LAZY_MAPPING = {
    "LiveBrowserSession": (".session", "LiveBrowserSession"),
    "LocalTestServer": (".server", "LocalTestServer"),
    "MockNodriverElement": (".mocks", "MockNodriverElement"),
    "MockNodriverTab": (".mocks", "MockNodriverTab"),
    "MockPlaywrightLocator": (".mocks", "MockPlaywrightLocator"),
    "MockPlaywrightPage": (".mocks", "MockPlaywrightPage"),
    "MockSeleniumDriver": (".mocks", "MockSeleniumDriver"),
    "MockSeleniumElement": (".mocks", "MockSeleniumElement"),
    "RecordedRequest": (".server", "RecordedRequest"),
    "SnapshotRecorder": (".snapshot", "SnapshotRecorder"),
    "TestResponse": (".server", "TestResponse"),
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
        + ["mocks", "server", "session", "snapshot", "__all__", "__doc__"]
    )


__all__ = [
    "LiveBrowserSession",
    "LocalTestServer",
    "MockNodriverElement",
    "MockNodriverTab",
    "MockPlaywrightLocator",
    "MockPlaywrightPage",
    "MockSeleniumDriver",
    "MockSeleniumElement",
    "RecordedRequest",
    "SnapshotRecorder",
    "TestResponse",
    "mocks",
    "server",
    "session",
    "snapshot",
    "use_html_snapshot",
]
