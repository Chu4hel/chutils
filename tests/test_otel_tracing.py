import logging
from unittest.mock import MagicMock, patch

import pytest

from chutils.context import ContextFilter
from chutils.logger.formatters import ChutilsJsonFormatter
from chutils.tracing import trace, setup_tracing, get_current_trace_context


# Моки для структур OpenTelemetry
class MockSpanContext:
    def __init__(self, trace_id, span_id, is_valid=True):
        self.trace_id = trace_id
        self.span_id = span_id
        self.is_valid = is_valid


class MockSpan:
    def __init__(self, context):
        self._context = context

    def get_span_context(self):
        return self._context


@pytest.fixture
def mock_otel_modules():
    """Фикстура для полной имитации наличия OpenTelemetry в системе."""
    mock_otel = MagicMock()
    mock_sdk = MagicMock()
    mock_exporter = MagicMock()

    # Создаем иерархию моков
    modules = {
        "opentelemetry": mock_otel,
        "opentelemetry.trace": mock_otel.trace,
        "opentelemetry.sdk": mock_sdk,
        "opentelemetry.sdk.resources": mock_sdk.resources,
        "opentelemetry.sdk.trace": mock_sdk.trace,
        "opentelemetry.sdk.trace.export": mock_sdk.trace.export,
        "opentelemetry.exporter": mock_exporter,
        "opentelemetry.exporter.otlp": mock_exporter.otlp,
        "opentelemetry.exporter.otlp.proto": mock_exporter.otlp.proto,
        "opentelemetry.exporter.otlp.proto.grpc": mock_exporter.otlp.proto.grpc,
        "opentelemetry.exporter.otlp.proto.grpc.trace_exporter": mock_exporter.otlp.proto.grpc.trace_exporter,
    }

    with patch.dict("sys.modules", modules), \
            patch("chutils.tracing.IS_OTEL_AVAILABLE", True), \
            patch("chutils.tracing.otel_trace", mock_otel.trace):
        # Настраиваем дефолтный невалидный спан
        invalid_context = MockSpanContext(0, 0, is_valid=False)
        mock_otel.trace.get_current_span.return_value = MockSpan(invalid_context)

        yield mock_otel


def test_trace_decorator_sync(mock_otel_modules):
    """Тест декоратора @trace для синхронных функций."""
    mock_tracer = MagicMock()
    mock_otel_modules.trace.get_tracer.return_value = mock_tracer

    @trace(name="test_span", attributes={"attr": "val"})
    def my_func(x):
        return x * 2

    assert my_func(2) == 4
    mock_tracer.start_as_current_span.assert_called_once_with("test_span", attributes={"attr": "val"})


@pytest.mark.asyncio
async def test_trace_decorator_async(mock_otel_modules):
    """Тест декоратора @trace для асинхронных функций."""
    mock_tracer = MagicMock()
    mock_otel_modules.trace.get_tracer.return_value = mock_tracer

    @trace(capture_kwargs=True)
    async def my_async_func(y):
        return y + 1

    assert await my_async_func(y=10) == 11
    mock_tracer.start_as_current_span.assert_called_once()
    args, kwargs = mock_tracer.start_as_current_span.call_args
    assert args[0] == "my_async_func"
    assert kwargs["attributes"] == {"arg.y": 10}


def test_trace_decorator_no_otel():
    """Проверяет, что декоратор не ломает код, если OTel не установлен."""
    with patch("chutils.tracing.IS_OTEL_AVAILABLE", False):
        @trace()
        def some_func():
            return "ok"

        assert some_func() == "ok"


def test_get_current_trace_context(mock_otel_modules):
    """Тест получения контекста трассировки."""
    # Валидный контекст
    valid_context = MockSpanContext(0x1234, 0x5678)
    mock_otel_modules.trace.get_current_span.return_value = MockSpan(valid_context)

    ctx = get_current_trace_context()
    assert ctx["trace_id"] == format(0x1234, "032x")
    assert ctx["span_id"] == format(0x5678, "016x")


def test_logger_integration_text(mock_otel_modules):
    """Тест инъекции контекста в текстовые логи."""
    valid_context = MockSpanContext(0x1234, 0x5678)
    mock_otel_modules.trace.get_current_span.return_value = MockSpan(valid_context)

    with patch("chutils.tracing.get_current_trace_context", side_effect=get_current_trace_context):
        log_filter = ContextFilter()
        record = logging.LogRecord("test", logging.INFO, "path", 10, "msg", (), None)
        log_filter.filter(record)

        assert hasattr(record, "trace_id")
        assert record.trace_id == format(0x1234, "032x")
        assert f"trace_id={record.trace_id}" in record.context


def test_logger_integration_json(mock_otel_modules):
    """Тест инъекции контекста в JSON логи."""
    valid_context = MockSpanContext(0x1234, 0x5678)
    mock_otel_modules.trace.get_current_span.return_value = MockSpan(valid_context)

    with patch("chutils.tracing.get_current_trace_context", side_effect=get_current_trace_context):
        log_filter = ContextFilter()
        record = logging.LogRecord("test", logging.INFO, "path", 10, "msg", (), None)
        log_filter.filter(record)

        with patch("chutils.logger.formatters.JSON_LOGGER_AVAILABLE", True), \
                patch("pythonjsonlogger.json.JsonFormatter.add_fields"):  # Исправлено на .json

            formatter = ChutilsJsonFormatter()
            log_record = {}
            formatter.add_fields(log_record, record, {})

            assert log_record["trace_id"] == format(0x1234, "032x")
            assert log_record["span_id"] == format(0x5678, "016x")


def test_setup_tracing_console(mock_otel_modules):
    """Тест инициализации OTel с консольным экспортером."""
    # Сбрасываем моки для чистого теста
    mock_otel_modules.trace.set_tracer_provider.reset_mock()

    success = setup_tracing("test-service", exporter_type="console")
    assert success is True
    mock_otel_modules.trace.set_tracer_provider.assert_called_once()


def test_setup_tracing_otlp(mock_otel_modules):
    """Тест инициализации OTel с OTLP экспортером."""
    success = setup_tracing("test-service", exporter_type="otlp", otlp_protocol="grpc")
    assert success is True
