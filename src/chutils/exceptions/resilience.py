from .base import ChutilsException


class RateLimitExceededError(ChutilsException):
    """Ошибка: превышен лимит частоты вызовов (Rate Limit Exceeded)."""


class CircuitBreakerOpenError(ChutilsException):
    """Ошибка: цепь предохранителя открыта (запросы заблокированы)."""


class BulkheadLimitExceeded(ChutilsException):
    """Ошибка: превышен предел параллельных запросов Bulkhead."""


class HttpClientError(ChutilsException):
    """Базовая ошибка HTTP-клиента chutils."""
