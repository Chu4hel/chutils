"""Модуль инструментов автотестирования скраперов и парсеров (chutils.scraping.testing)."""

import importlib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
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

_LAZY_MAPPING = {
    "MockNodriverElement": (".mocks", "MockNodriverElement"),
    "MockNodriverTab": (".mocks", "MockNodriverTab"),
    "MockPlaywrightLocator": (".mocks", "MockPlaywrightLocator"),
    "MockPlaywrightPage": (".mocks", "MockPlaywrightPage"),
    "MockSeleniumDriver": (".mocks", "MockSeleniumDriver"),
    "MockSeleniumElement": (".mocks", "MockSeleniumElement"),
}


def __getattr__(name: str) -> Any:
    if name in _LAZY_MAPPING:
        mod_path, attr_name = _LAZY_MAPPING[name]
        module = importlib.import_module(mod_path, __name__)
        return getattr(module, attr_name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(list(_LAZY_MAPPING.keys()) + ["mocks", "__all__", "__doc__"])


__all__ = [
    "MockNodriverElement",
    "MockNodriverTab",
    "MockPlaywrightLocator",
    "MockPlaywrightPage",
    "MockSeleniumDriver",
    "MockSeleniumElement",
    "mocks",
]
