"""
Модуль chutils.http.tracing — интеграция с OpenTelemetry для HTTP-запросов.

Предоставляет функции для:
- Инжекта W3C Trace Context заголовков (traceparent, tracestate) в исходящие запросы.
- Создания спанов для каждого HTTP-запроса.
- Безопасного импорта opentelemetry (graceful fallback при отсутствии пакета).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from chutils.env import OTEL_AVAILABLE

if TYPE_CHECKING:
    pass

# ─── Ленивый импорт OTEL ─────────────────────────────────────────────────────

_otel_trace = None
_otel_propagate = None
_otel_context = None

if OTEL_AVAILABLE:
    try:
        from opentelemetry import trace as _otel_trace  # type: ignore[no-redef]
        from opentelemetry import propagate as _otel_propagate  # type: ignore[no-redef]
        from opentelemetry import context as _otel_context  # type: ignore[no-redef]
    except Exception:  # noqa: BLE001
        _otel_trace = None
        _otel_propagate = None
        _otel_context = None


def inject_trace_headers(headers: dict[str, str]) -> dict[str, str]:
    """Инжектирует W3C Trace Context заголовки в словарь заголовков запроса.

    Если OpenTelemetry не установлен или трассировка не настроена,
    возвращает заголовки без изменений.

    Инжектируемые заголовки:
    - ``traceparent``: идентификаторы trace и span (формат W3C).
    - ``tracestate``: дополнительное состояние вендора (опционально).

    Args:
        headers: Исходный словарь HTTP-заголовков запроса.

    Returns:
        Обновлённый словарь с добавленными заголовками трассировки
        (или оригинальный, если OTEL недоступен).

    Example:
        ```python
        from chutils.http.tracing import inject_trace_headers

        headers = {"Authorization": "Bearer token"}
        headers = inject_trace_headers(headers)
        # headers теперь содержит "traceparent" если OTEL активен
        ```
    """
    if _otel_propagate is None or _otel_trace is None:
        return headers

    try:
        carrier: dict[str, str] = {}
        _otel_propagate.inject(carrier)
        if carrier:
            return {**headers, **carrier}
    except Exception:  # noqa: BLE001
        pass

    return headers


def create_http_span(
        method: str,
        url: str,
        tracer_name: str = "chutils.http",
) -> object | None:
    """Создаёт OTEL-спан для исходящего HTTP-запроса.

    Если OpenTelemetry не установлен, возвращает None.

    Args:
        method: HTTP-метод (GET, POST и т.д.).
        url: Полный URL запроса.
        tracer_name: Имя трейсера (используется для группировки спанов).

    Returns:
        Контекстный менеджер спана или None, если OTEL недоступен.

    Example:
        ```python
        from chutils.http.tracing import create_http_span

        span = create_http_span("GET", "https://api.example.com/users")
        if span is not None:
            with span:
                response = requests.get(url)
        ```
    """
    if _otel_trace is None:
        return None

    try:
        tracer = _otel_trace.get_tracer(tracer_name)
        return tracer.start_as_current_span(
            f"HTTP {method.upper()}",
            attributes={
                "http.method": method.upper(),
                "http.url": url,
            },
        )
    except Exception:  # noqa: BLE001
        return None


def record_span_status(span: object | None, status_code: int) -> None:
    """Записывает HTTP-статус-код в атрибуты спана.

    Args:
        span: OTEL-спан (или None, если OTEL недоступен).
        status_code: HTTP-статус-код ответа.
    """
    if span is None or _otel_trace is None:
        return

    try:
        span.set_attribute("http.status_code", status_code)  # type: ignore[union-attr]
        if status_code >= 400:
            span.set_status(  # type: ignore[union-attr]
                _otel_trace.Status(_otel_trace.StatusCode.ERROR, f"HTTP {status_code}")
            )
        else:
            span.set_status(_otel_trace.Status(_otel_trace.StatusCode.OK))  # type: ignore[union-attr]
    except Exception:  # noqa: BLE001
        pass
