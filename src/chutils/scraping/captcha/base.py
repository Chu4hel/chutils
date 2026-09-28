"""Реэкспорт базовых классов капчи из chutils.captcha для обратной совместимости."""

from __future__ import annotations

from chutils.captcha.base import (
    BaseAsyncCaptchaSolver,
    BaseCaptchaSolver,
    _ensure_httpx,
)

__all__ = [
    "BaseAsyncCaptchaSolver",
    "BaseCaptchaSolver",
    "_ensure_httpx",
]
