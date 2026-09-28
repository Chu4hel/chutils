import importlib.util
from typing import Any

from chutils.exceptions import OptionalDependencyError

from .exceptions import (
    CaptchaBalanceError,
    CaptchaError,
    CaptchaServiceError,
    CaptchaTimeoutError,
)


def _ensure_httpx() -> None:
    if importlib.util.find_spec("httpx") is None:
        raise OptionalDependencyError(
            "Модуль 'httpx' не установлен. Для работы с капча-клиентами "
            "установите его: pip install chutils[captcha] или pip install httpx.",
            dependency="httpx",
            hint="Выполните pip install chutils[captcha] или pip install httpx.",
        )


try:
    _ensure_httpx()
    from .anticaptcha import AntiCaptchaSolver, AsyncAntiCaptchaSolver
    from .capmonster import AsyncCapMonsterSolver, CapMonsterSolver
    from .geetest import AsyncGeeTestSolver, GeeTestSolver
    from .models import GeeTestResult, GeeTestTaskConfig, ReCaptchaEnterpriseConfig
    from .recaptcha_enterprise import (
        AsyncReCaptchaEnterpriseSolver,
        ReCaptchaEnterpriseSolver,
    )
    from .rucaptcha import AsyncRuCaptchaSolver, RuCaptchaSolver
except Exception:

    def _create_fallback(name: str) -> Any:
        class FallbackSolver:
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                _ensure_httpx()

        FallbackSolver.__name__ = name
        FallbackSolver.__doc__ = f"Заглушка для {name} при отсутствии httpx."
        return FallbackSolver

    # Используем type ignore, так как mypy статически не разрешает
    # переопределять типы импортированных классов динамическими заглушками.
    RuCaptchaSolver = _create_fallback("RuCaptchaSolver")  # type: ignore[misc]
    AsyncRuCaptchaSolver = _create_fallback("AsyncRuCaptchaSolver")  # type: ignore[misc]
    AntiCaptchaSolver = _create_fallback("AntiCaptchaSolver")  # type: ignore[misc]
    AsyncAntiCaptchaSolver = _create_fallback("AsyncAntiCaptchaSolver")  # type: ignore[misc]
    CapMonsterSolver = _create_fallback("CapMonsterSolver")  # type: ignore[misc]
    AsyncCapMonsterSolver = _create_fallback("AsyncCapMonsterSolver")  # type: ignore[misc]
    GeeTestSolver = _create_fallback("GeeTestSolver")  # type: ignore[misc]
    AsyncGeeTestSolver = _create_fallback("AsyncGeeTestSolver")  # type: ignore[misc]
    ReCaptchaEnterpriseSolver = _create_fallback("ReCaptchaEnterpriseSolver")  # type: ignore[misc]
    AsyncReCaptchaEnterpriseSolver = _create_fallback("AsyncReCaptchaEnterpriseSolver")  # type: ignore[misc]
    GeeTestResult = None  # type: ignore[misc,assignment]
    GeeTestTaskConfig = None  # type: ignore[misc,assignment]
    ReCaptchaEnterpriseConfig = None  # type: ignore[misc,assignment]

__all__ = [
    "AntiCaptchaSolver",
    "AsyncAntiCaptchaSolver",
    "AsyncCapMonsterSolver",
    "AsyncGeeTestSolver",
    "AsyncReCaptchaEnterpriseSolver",
    "AsyncRuCaptchaSolver",
    "CapMonsterSolver",
    "CaptchaBalanceError",
    "CaptchaError",
    "CaptchaServiceError",
    "CaptchaTimeoutError",
    "GeeTestResult",
    "GeeTestSolver",
    "GeeTestTaskConfig",
    "ReCaptchaEnterpriseConfig",
    "ReCaptchaEnterpriseSolver",
    "RuCaptchaSolver",
]
