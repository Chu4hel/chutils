"""
Тесты для chutils.http.tracing.

Проверяет:
- inject_trace_headers при наличии и отсутствии OTEL
- create_http_span: создание спана и graceful fallback
- record_span_status: установка атрибутов на спане
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch


# ─── inject_trace_headers ────────────────────────────────────────────────────


def test_inject_trace_headers_without_otel() -> None:
    """При отсутствии OTEL заголовки возвращаются без изменений."""
    with patch("chutils.http.tracing._otel_propagate", None):
        from chutils.http.tracing import inject_trace_headers
        headers = {"Authorization": "Bearer token", "Content-Type": "application/json"}
        result = inject_trace_headers(headers)
        assert result == headers


def test_inject_trace_headers_with_otel_active() -> None:
    """При наличии OTEL инжектируются заголовки traceparent/tracestate."""
    mock_propagate = MagicMock()
    mock_trace = MagicMock()

    def fake_inject(carrier: dict[str, str]) -> None:
        carrier["traceparent"] = "00-aabbccdd-eeff0011-01"
        carrier["tracestate"] = "vendor=value"

    mock_propagate.inject.side_effect = fake_inject

    with patch("chutils.http.tracing._otel_propagate", mock_propagate):
        with patch("chutils.http.tracing._otel_trace", mock_trace):
            from chutils.http.tracing import inject_trace_headers
            headers = {"X-App": "test"}
            result = inject_trace_headers(headers)

    assert "traceparent" in result
    assert result["traceparent"] == "00-aabbccdd-eeff0011-01"
    assert result["tracestate"] == "vendor=value"
    assert result["X-App"] == "test"  # оригинальный заголовок сохранён


def test_inject_trace_headers_otel_exception_graceful() -> None:
    """Если OTEL выбрасывает исключение, возвращаются исходные заголовки."""
    mock_propagate = MagicMock()
    mock_propagate.inject.side_effect = RuntimeError("otel broken")
    mock_trace = MagicMock()

    with patch("chutils.http.tracing._otel_propagate", mock_propagate):
        with patch("chutils.http.tracing._otel_trace", mock_trace):
            from chutils.http.tracing import inject_trace_headers
            headers = {"X-Safe": "value"}
            result = inject_trace_headers(headers)

    assert result == headers


def test_inject_trace_headers_no_context_no_headers_added() -> None:
    """Если OTEL активен, но нет активного span (пустой carrier), заголовки не добавляются."""
    mock_propagate = MagicMock()
    mock_trace = MagicMock()

    def fake_inject_empty(carrier: dict[str, str]) -> None:
        pass  # ничего не добавляем

    mock_propagate.inject.side_effect = fake_inject_empty

    with patch("chutils.http.tracing._otel_propagate", mock_propagate):
        with patch("chutils.http.tracing._otel_trace", mock_trace):
            from chutils.http.tracing import inject_trace_headers
            headers = {"X-Header": "value"}
            result = inject_trace_headers(headers)

    assert result == headers


# ─── create_http_span ────────────────────────────────────────────────────────


def test_create_http_span_without_otel_returns_none() -> None:
    """При отсутствии OTEL возвращает None."""
    with patch("chutils.http.tracing._otel_trace", None):
        from chutils.http.tracing import create_http_span
        span = create_http_span("GET", "http://example.com/")
        assert span is None


def test_create_http_span_with_otel() -> None:
    """При наличии OTEL возвращает объект span (не None)."""
    mock_trace = MagicMock()
    mock_tracer = MagicMock()
    mock_span_cm = MagicMock()
    mock_trace.get_tracer.return_value = mock_tracer
    mock_tracer.start_as_current_span.return_value = mock_span_cm

    with patch("chutils.http.tracing._otel_trace", mock_trace):
        from chutils.http.tracing import create_http_span
        span = create_http_span("POST", "http://example.com/api")

    assert span is not None
    mock_tracer.start_as_current_span.assert_called_once_with(
        "HTTP POST",
        attributes={
            "http.method": "POST",
            "http.url": "http://example.com/api",
        },
    )


def test_create_http_span_otel_exception_returns_none() -> None:
    """Если OTEL выбрасывает исключение, возвращает None (graceful)."""
    mock_trace = MagicMock()
    mock_trace.get_tracer.side_effect = RuntimeError("tracer unavailable")

    with patch("chutils.http.tracing._otel_trace", mock_trace):
        from chutils.http.tracing import create_http_span
        span = create_http_span("GET", "http://example.com/")

    assert span is None


def test_create_http_span_uses_custom_tracer_name() -> None:
    """create_http_span использует переданное имя трейсера."""
    mock_trace = MagicMock()
    mock_tracer = MagicMock()
    mock_trace.get_tracer.return_value = mock_tracer
    mock_tracer.start_as_current_span.return_value = MagicMock()

    with patch("chutils.http.tracing._otel_trace", mock_trace):
        from chutils.http.tracing import create_http_span
        create_http_span("GET", "http://example.com/", tracer_name="my.service")

    mock_trace.get_tracer.assert_called_once_with("my.service")


# ─── record_span_status ───────────────────────────────────────────────────────


def test_record_span_status_none_span_no_error() -> None:
    """При span=None функция ничего не делает (без исключений)."""
    from chutils.http.tracing import record_span_status
    record_span_status(None, 200)  # Не должно выбрасывать


def test_record_span_status_2xx_ok() -> None:
    """2xx статус устанавливает StatusCode.OK на спане."""
    mock_trace = MagicMock()
    mock_status_cls = MagicMock()
    mock_trace.Status = mock_status_cls
    mock_trace.StatusCode.OK = "OK"
    mock_trace.StatusCode.ERROR = "ERROR"

    mock_span = MagicMock()

    with patch("chutils.http.tracing._otel_trace", mock_trace):
        from chutils.http.tracing import record_span_status
        record_span_status(mock_span, 200)

    mock_span.set_attribute.assert_called_once_with("http.status_code", 200)
    # Проверяем что set_status был вызван с OK
    call_args = mock_span.set_status.call_args[0][0]
    assert mock_status_cls.call_args[0][0] == "OK"


def test_record_span_status_4xx_error() -> None:
    """4xx статус устанавливает StatusCode.ERROR на спане."""
    mock_trace = MagicMock()
    mock_status_cls = MagicMock()
    mock_trace.Status = mock_status_cls
    mock_trace.StatusCode.OK = "OK"
    mock_trace.StatusCode.ERROR = "ERROR"

    mock_span = MagicMock()

    with patch("chutils.http.tracing._otel_trace", mock_trace):
        from chutils.http.tracing import record_span_status
        record_span_status(mock_span, 404)

    mock_span.set_attribute.assert_called_once_with("http.status_code", 404)
    # Первый аргумент Status() должен быть ERROR
    assert mock_status_cls.call_args[0][0] == "ERROR"


def test_record_span_status_5xx_error() -> None:
    """5xx статус устанавливает StatusCode.ERROR на спане."""
    mock_trace = MagicMock()
    mock_status_cls = MagicMock()
    mock_trace.Status = mock_status_cls
    mock_trace.StatusCode.OK = "OK"
    mock_trace.StatusCode.ERROR = "ERROR"

    mock_span = MagicMock()

    with patch("chutils.http.tracing._otel_trace", mock_trace):
        from chutils.http.tracing import record_span_status
        record_span_status(mock_span, 503)

    assert mock_status_cls.call_args[0][0] == "ERROR"


def test_record_span_status_otel_exception_graceful() -> None:
    """Если OTEL выбрасывает при записи статуса, исключение поглощается."""
    mock_trace = MagicMock()
    mock_trace.Status.side_effect = RuntimeError("broken")

    mock_span = MagicMock()
    mock_span.set_attribute.side_effect = RuntimeError("also broken")

    with patch("chutils.http.tracing._otel_trace", mock_trace):
        from chutils.http.tracing import record_span_status
        record_span_status(mock_span, 200)  # Не должно выбрасывать


# ─── OTEL_AVAILABLE flag ──────────────────────────────────────────────────────


def test_otel_available_reflects_env() -> None:
    """OTEL_AVAILABLE корректно импортируется из chutils.env."""
    from chutils.env import OTEL_AVAILABLE
    assert isinstance(OTEL_AVAILABLE, bool)
