"""Модуль-фасад для обратной совместимости. Реэкспортирует компоненты из browser_stealth.proxy.extension."""
from __future__ import annotations

import sys
import types
from typing import Any

import browser_stealth.proxy.extension as _target_module


class _ModuleProxy(types.ModuleType):
    def __getattr__(self, name: str) -> Any:
        return getattr(_target_module, name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name in ("__name__", "__doc__", "__package__", "__loader__", "__spec__", "__file__", "__path__", "__dict__"):
            super().__setattr__(name, value)
        else:
            setattr(_target_module, name, value)
            super().__setattr__(name, value)

    def __dir__(self) -> list[str]:
        return dir(_target_module)

sys.modules[__name__].__class__ = _ModuleProxy
globals().update({k: getattr(_target_module, k) for k in dir(_target_module) if not k.startswith("__")})
