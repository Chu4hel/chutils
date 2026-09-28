"""Реэкспорт исключений капчи из chutils.captcha для обратной совместимости."""

from __future__ import annotations

from chutils.captcha.exceptions import (
    CaptchaBalanceError,
    CaptchaError,
    CaptchaServiceError,
    CaptchaTimeoutError,
)

__all__ = [
    "CaptchaBalanceError",
    "CaptchaError",
    "CaptchaServiceError",
    "CaptchaTimeoutError",
]
