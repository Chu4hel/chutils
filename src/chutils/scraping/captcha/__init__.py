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
    class RuCaptchaSolver:  # type: ignore
        """Заглушка для RuCaptchaSolver при отсутствии httpx."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            """Инициализирует заглушку.

            Args:
                *args: Произвольные позиционные аргументы.
                **kwargs: Произвольные именованные аргументы.
            """
            _ensure_httpx()


    class AsyncRuCaptchaSolver:  # type: ignore
        """Заглушка для AsyncRuCaptchaSolver при отсутствии httpx."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            """Инициализирует заглушку.

            Args:
                *args: Произвольные позиционные аргументы.
                **kwargs: Произвольные именованные аргументы.
            """
            _ensure_httpx()


    class AntiCaptchaSolver:  # type: ignore
        """Заглушка для AntiCaptchaSolver при отсутствии httpx."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            """Инициализирует заглушку.

            Args:
                *args: Произвольные позиционные аргументы.
                **kwargs: Произвольные именованные аргументы.
            """
            _ensure_httpx()


    class AsyncAntiCaptchaSolver:  # type: ignore
        """Заглушка для AsyncAntiCaptchaSolver при отсутствии httpx."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            """Инициализирует заглушку.

            Args:
                *args: Произвольные позиционные аргументы.
                **kwargs: Произвольные именованные аргументы.
            """
            _ensure_httpx()


    class CapMonsterSolver:  # type: ignore
        """Заглушка для CapMonsterSolver при отсутствии httpx."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            """Инициализирует заглушку.

            Args:
                *args: Произвольные позиционные аргументы.
                **kwargs: Произвольные именованные аргументы.
            """
            _ensure_httpx()


    class AsyncCapMonsterSolver:  # type: ignore
        """Заглушка для AsyncCapMonsterSolver при отсутствии httpx."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            """Инициализирует заглушку.

            Args:
                *args: Произвольные позиционные аргументы.
                **kwargs: Произвольные именованные аргументы.
            """
            _ensure_httpx()

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
