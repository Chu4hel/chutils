"""Модуль скрейпинга, автоматизации и утилиты антидетекта."""

import importlib
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .profiles import (
        BrowserProfile as BrowserProfile,
        ProfileManager as ProfileManager,
    )

_LAZY_MAPPING = {
    "BrowserProfile": (".profiles", "BrowserProfile"),
    "ProfileManager": (".profiles", "ProfileManager"),
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
        + ["captcha", "concurrency", "humanize", "__all__", "__doc__"]
    )


__all__ = ["captcha", "concurrency", "humanize", "BrowserProfile", "ProfileManager"]
