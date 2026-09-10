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
    "TestResponse": (".server", "TestResponse"),
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
        + ["mocks", "server", "session", "__all__", "__doc__"]
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
    "TestResponse",
    "mocks",
    "server",
    "session",
]
