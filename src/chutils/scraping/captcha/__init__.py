import importlib.util
from typing import Any

from chutils.exceptions import OptionalDependencyError
from .exceptions import (
    CaptchaError,
    CaptchaTimeoutError,
    CaptchaBalanceError,
    CaptchaServiceError,
)


def _ensure_httpx() -> None:
    if importlib.util.find_spec("httpx") is None:
        raise OptionalDependencyError(
            "Модуль 'httpx' не установлен. Для работы с капча-клиентами "
            "установите его: pip install chutils[captcha] или pip install httpx.",
            dependency="httpx",
            hint="Выполните pip install chutils[captcha] или pip install httpx."
        )


try:
    _ensure_httpx()
    from .rucaptcha import RuCaptchaSolver, AsyncRuCaptchaSolver
    from .anticaptcha import AntiCaptchaSolver, AsyncAntiCaptchaSolver
    from .capmonster import CapMonsterSolver, AsyncCapMonsterSolver
except Exception:
    def _create_fallback(name: str) -> Any:
        class FallbackSolver:
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                _ensure_httpx()

        FallbackSolver.__name__ = name
        FallbackSolver.__doc__ = f"Заглушка для {name} при отсутствии httpx."
        return FallbackSolver


    RuCaptchaSolver = _create_fallback("RuCaptchaSolver")
    AsyncRuCaptchaSolver = _create_fallback("AsyncRuCaptchaSolver")
    AntiCaptchaSolver = _create_fallback("AntiCaptchaSolver")
    AsyncAntiCaptchaSolver = _create_fallback("AsyncAntiCaptchaSolver")
    CapMonsterSolver = _create_fallback("CapMonsterSolver")
    AsyncCapMonsterSolver = _create_fallback("AsyncCapMonsterSolver")

__all__ = [
    "RuCaptchaSolver",
    "AsyncRuCaptchaSolver",
    "AntiCaptchaSolver",
    "AsyncAntiCaptchaSolver",
    "CapMonsterSolver",
    "AsyncCapMonsterSolver",
    "CaptchaError",
    "CaptchaTimeoutError",
    "CaptchaBalanceError",
    "CaptchaServiceError",
]
