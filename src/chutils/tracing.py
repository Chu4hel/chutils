"""
Интеграция с OpenTelemetry для распределенного трассирования.

Позволяет автоматически создавать спаны для функций и связывать логи с контекстом трассировки.
Функционал является опциональным и требует установки `chutils[otel]`.
"""

import functools
import inspect
from typing import Any, Callable, Optional, TypeVar, cast

T = TypeVar("T", bound=Callable[..., Any])

try:
    from opentelemetry import trace as otel_trace

    IS_OTEL_AVAILABLE = True
except ImportError:
    otel_trace = None  # type: ignore
    IS_OTEL_AVAILABLE = False


def get_tracer(name: str = "chutils") -> Any:
    """
    Возвращает экземпляр трейсера, если OpenTelemetry доступен.

    Args:
        name: Имя трейсера.

    Returns:
        Экземпляр Tracer или None, если OTel не установлен.
    """
    if IS_OTEL_AVAILABLE and otel_trace:
        return otel_trace.get_tracer(name)
    return None


def trace(
        name: Optional[Any] = None,
        attributes: Optional[dict[str, Any]] = None,
        capture_kwargs: bool = False,
) -> Any:
    """
    Декоратор для автоматического создания спана при вызове функции.
    Поддерживает как синхронные, так и асинхронные функции.

    Если OpenTelemetry не установлен, декоратор просто возвращает оригинальную функцию
    без накладных расходов.

    Args:
        name: Имя спана. По умолчанию используется имя функции.
            Может использоваться как позиционный аргумент при @trace("имя").
        attributes: Дополнительные атрибуты для спана.
        capture_kwargs: Если True, аргументы функции будут добавлены как атрибуты спана
            с префиксом 'arg.'.

    Example:
        ```python
        @trace()
        def my_func(x):
            return x + 1

        @trace("custom_name", capture_kwargs=True)
        async def my_async_func(y):
            return y * 2
        ```
    """

    def decorator(func: T) -> T:
        if not IS_OTEL_AVAILABLE:
            return func

        tracer = get_tracer()
        if not tracer:
            return func

        # Определяем имя спана: если name передан как строка, используем её, иначе имя функции
        span_name = (name if isinstance(name, str) else None) or func.__name__

        if inspect.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                actual_attributes = attributes.copy() if attributes else {}
                if capture_kwargs:
                    actual_attributes.update({f"arg.{k}": v for k, v in kwargs.items()})

                with tracer.start_as_current_span(span_name, attributes=actual_attributes):
                    return await func(*args, **kwargs)

            return cast(T, async_wrapper)
        else:
            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                actual_attributes = attributes.copy() if attributes else {}
                if capture_kwargs:
                    actual_attributes.update({f"arg.{k}": v for k, v in kwargs.items()})

                with tracer.start_as_current_span(span_name, attributes=actual_attributes):
                    return func(*args, **kwargs)

            return cast(T, sync_wrapper)

    # Поддержка использования без скобок: @trace
    if callable(name):
        f = name
        name = None
        return decorator(f)

    return decorator
