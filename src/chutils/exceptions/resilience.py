from .base import ChutilsException


class RateLimitExceededError(ChutilsException):
    """Ошибка: превышен лимит частоты вызовов (Rate Limit Exceeded)."""

    pass


class CircuitBreakerOpenError(ChutilsException):
    """Ошибка: цепь предохранителя открыта (запросы заблокированы)."""

    pass


class BulkheadLimitExceeded(ChutilsException):
    """Ошибка: превышен предел параллельных запросов Bulkhead."""

    pass


class HttpClientError(ChutilsException):
    """Базовая ошибка HTTP-клиента chutils."""

    pass
