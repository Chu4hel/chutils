"""Модуль-фасад для обратной совместимости. Реэкспортирует humanize и antidetect."""
from __future__ import annotations

import sys
import types
from typing import Any

import browser_stealth.antidetect as _antidetect
import browser_stealth.humanize as _humanize


class _HumanizeProxy(types.ModuleType):
    def __getattr__(self, name: str) -> Any:
        if hasattr(_humanize, name):
            return getattr(_humanize, name)
        return getattr(_antidetect, name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name in ("__name__", "__doc__", "__package__", "__loader__", "__spec__", "__file__", "__path__", "__dict__"):
            super().__setattr__(name, value)
        else:
            if hasattr(_humanize, name):
                setattr(_humanize, name, value)
            if hasattr(_antidetect, name):
                setattr(_antidetect, name, value)
            super().__setattr__(name, value)

    def __dir__(self) -> list[str]:
        return sorted(set(dir(_humanize) | set(dir(_antidetect))))

sys.modules[__name__].__class__ = _HumanizeProxy
globals().update({k: getattr(_humanize, k) for k in dir(_humanize) if not k.startswith("__")})
globals().update({k: getattr(_antidetect, k) for k in dir(_antidetect) if not k.startswith("__")})
