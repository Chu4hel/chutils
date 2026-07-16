from .base import ChutilsException


class RateLimitExceededError(ChutilsException):
    """Ошибка: превышен лимит частоты вызовов (Rate Limit Exceeded)."""

    pass


class CircuitBreakerOpenError(ChutilsException):
    """Ошибка: цепь предохранителя открыта (запросы заблокированы)."""

    pass
