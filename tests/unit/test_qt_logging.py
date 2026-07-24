"""
Тесты для QtLogHandler и setup_qt_logging (src/chutils/qt/logging.py).
"""

import logging
from unittest.mock import MagicMock, patch

import pytest

from chutils.exceptions import OptionalDependencyError
import chutils.qt.shim as shim


def test_qt_log_handler_without_qt() -> None:
    """Проверяет выбрасывание OptionalDependencyError при отсутствии Qt."""
    with patch.object(shim, "QT_BINDING", None):
        from chutils.qt.logging import QtLogHandler
        with pytest.raises(OptionalDependencyError):
            QtLogHandler()


def test_qt_log_handler_emit() -> None:
    """Проверяет отправку сообщения в сигнал при вызове emit."""
    mock_emitter = MagicMock()
    with patch("chutils.qt.logging.require_qt"):
        with patch("chutils.qt.logging._QtLogEmitter", return_value=mock_emitter):
            from chutils.qt.logging import QtLogHandler
            handler = QtLogHandler()
            record = logging.LogRecord("test", logging.INFO, "path", 10, "Hello Qt!", (), None)
            handler.emit(record)

            mock_emitter.message_emitted.emit.assert_called_once()


def test_qt_log_handler_emit_error() -> None:
    """Проверяет вызов handleError при исключении в emit."""
    mock_emitter = MagicMock()
    mock_emitter.message_emitted.emit.side_effect = RuntimeError("Emit fail")
    with patch("chutils.qt.logging.require_qt"):
        with patch("chutils.qt.logging._QtLogEmitter", return_value=mock_emitter):
            from chutils.qt.logging import QtLogHandler
            handler = QtLogHandler()
            handler.handleError = MagicMock()
            record = logging.LogRecord("test", logging.INFO, "path", 10, "Error record", (), None)
            handler.emit(record)
            handler.handleError.assert_called_once_with(record)


def test_setup_qt_logging_callable_widget() -> None:
    """Проверяет привязку логов к callable функции."""
    mock_emitter = MagicMock()
    calls = []
    func = lambda msg: calls.append(msg)

    with patch("chutils.qt.logging.require_qt"):
        with patch("chutils.qt.logging._QtLogEmitter", return_value=mock_emitter):
            from chutils.qt.logging import setup_qt_logging
            setup_qt_logging(widget=func, logger_name="callable_logger")
            callback = mock_emitter.message_emitted.connect.call_args[0][0]
            callback("test_msg", 20)
            assert calls == ["test_msg"]


def test_setup_qt_logging_append_widget() -> None:
    """Проверяет привязку к виджету с методом append."""
    mock_emitter = MagicMock()
    class AppendWidget:
        def append(self, text: str) -> None:
            pass

    widget = MagicMock(spec=AppendWidget)

    with patch("chutils.qt.logging.require_qt"):
        with patch("chutils.qt.logging._QtLogEmitter", return_value=mock_emitter):
            from chutils.qt.logging import setup_qt_logging
            setup_qt_logging(widget=widget, logger_name="append_logger")
            callback = mock_emitter.message_emitted.connect.call_args[0][0]
            callback("append_msg", 20)
            widget.append.assert_called_once_with("append_msg")


def test_setup_qt_logging_show_message_widget() -> None:
    """Проверяет привязку к виджету с методом showMessage."""
    mock_emitter = MagicMock()
    class StatusWidget:
        def showMessage(self, text: str) -> None:
            pass

    widget = MagicMock(spec=StatusWidget)

    with patch("chutils.qt.logging.require_qt"):
        with patch("chutils.qt.logging._QtLogEmitter", return_value=mock_emitter):
            from chutils.qt.logging import setup_qt_logging
            setup_qt_logging(widget=widget, logger_name="show_msg_logger")
            callback = mock_emitter.message_emitted.connect.call_args[0][0]
            callback("status_msg", 20)
            widget.showMessage.assert_called_once_with("status_msg")


def test_setup_qt_logging_set_text_widget() -> None:
    """Проверяет привязку к виджету с методом setText."""
    mock_emitter = MagicMock()
    class LabelWidget:
        def setText(self, text: str) -> None:
            pass

    widget = MagicMock(spec=LabelWidget)

    with patch("chutils.qt.logging.require_qt"):
        with patch("chutils.qt.logging._QtLogEmitter", return_value=mock_emitter):
            from chutils.qt.logging import setup_qt_logging
            setup_qt_logging(widget=widget, logger_name="set_text_logger")
            callback = mock_emitter.message_emitted.connect.call_args[0][0]
            callback("label_msg", 20)
            widget.setText.assert_called_once_with("label_msg")
