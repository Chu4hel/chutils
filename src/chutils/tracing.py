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


def get_current_trace_context() -> Optional[dict[str, str]]:
    """
    Возвращает текущие trace_id и span_id, если трассировка активна.

    Returns:
        Словарь с trace_id и span_id или None.
    """
    if not IS_OTEL_AVAILABLE or not otel_trace:
        return None

    span = otel_trace.get_current_span()
    span_context = span.get_span_context()

    if not span_context.is_valid:
        return None

    return {
        "trace_id": format(span_context.trace_id, "032x"),
        "span_id": format(span_context.span_id, "016x"),
    }


def setup_tracing(
        service_name: str,
        exporter_type: str = "console",
        otlp_endpoint: Optional[str] = None,
        otlp_protocol: str = "grpc",
) -> bool:
    """
    Настраивает OpenTelemetry SDK для сбора трасс.

    Args:
        service_name: Имя сервиса для отображения в трассах.
        exporter_type: Тип экспортера: 'console' или 'otlp'.
        otlp_endpoint: URL эндпоинта для OTLP (например, http://localhost:4317).
        otlp_protocol: Протокол для OTLP: 'grpc' или 'http/protobuf'.

    Returns:
        True, если настройка выполнена успешно, False если OTel недоступен.
    """
    if not IS_OTEL_AVAILABLE:
        return False

    try:
        from opentelemetry.sdk.resources import SERVICE_NAME, Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        # Создаем ресурс
        resource = Resource(attributes={SERVICE_NAME: service_name})

        # Настраиваем провайдер
        provider = TracerProvider(resource=resource)
        otel_trace.set_tracer_provider(provider)

        # Настраиваем экспортер
        if exporter_type == "console":
            from opentelemetry.sdk.trace.export import ConsoleSpanExporter
            exporter = ConsoleSpanExporter()
        elif exporter_type == "otlp":
            if otlp_protocol == "grpc":
                from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            else:
                from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

            exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
        else:
            return False

        # Добавляем процессор
        processor = BatchSpanProcessor(exporter)
        provider.add_span_processor(processor)

        return True
    except Exception:
        return False


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
