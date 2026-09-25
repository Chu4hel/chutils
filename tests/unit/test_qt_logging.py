"""
Тесты для QtLogHandler и setup_qt_logging (src/chutils/qt/logging.py).
"""

import logging
from unittest.mock import MagicMock, patch

import pytest

from chutils.exceptions import OptionalDependencyError
from chutils.qt import shim


def test_qt_log_handler_without_qt() -> None:
    """Проверяет выбрасывание OptionalDependencyError при отсутствии Qt."""
    err = OptionalDependencyError(
        "Библиотека PyQt6 или PySide6 не установлена.", dependency="qt"
    )
    with (
        patch.object(shim, "QT_BINDING", None),
        patch("chutils.qt.logging.require_qt", side_effect=err),
    ):
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
            record = logging.LogRecord(
                "test", logging.INFO, "path", 10, "Hello Qt!", (), None
            )
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
            record = logging.LogRecord(
                "test", logging.INFO, "path", 10, "Error record", (), None
            )
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


def test_setup_qt_logging_global_registration_before_and_after() -> None:
    """Проверяет регистрацию в chutils.logger до и после создания логгеров."""
    from chutils.logger.core import (
        clear_global_handlers,
        get_global_handlers,
        setup_logger,
    )
    from chutils.qt.logging import remove_qt_logging, setup_qt_logging

    clear_global_handlers()

    # 1. Логгер создан ДО setup_qt_logging
    logger_before = setup_logger("test_qt_before", file_logging=False)

    mock_emitter = MagicMock()
    with (
        patch("chutils.qt.logging.require_qt"),
        patch("chutils.qt.logging._QtLogEmitter", return_value=mock_emitter),
    ):
        handler = setup_qt_logging(widget=None, logger_name=None)
        assert handler in get_global_handlers()
        assert handler in logger_before.handlers

        # 2. Логгер создан ПОСЛЕ setup_qt_logging
        logger_after = setup_logger("test_qt_after", file_logging=False)
        assert handler in logger_after.handlers

        # 3. Удаление
        remove_qt_logging(handler)
        assert handler not in get_global_handlers()
        assert handler not in logger_before.handlers
        assert handler not in logger_after.handlers

    clear_global_handlers()


def test_setup_logger_with_prior_qt_handler_configures_properly() -> None:
    """Проверяет, что наличие QtLogHandler не блокирует конфигурацию логгера chutils."""
    from chutils.logger.core import clear_global_handlers, setup_logger
    from chutils.qt.logging import remove_qt_logging, setup_qt_logging

    clear_global_handlers()

    mock_emitter = MagicMock()
    with (
        patch("chutils.qt.logging.require_qt"),
        patch("chutils.qt.logging._QtLogEmitter", return_value=mock_emitter),
    ):
        qt_handler = setup_qt_logging(logger_name="test_specific_qt")
        target_logger = logging.getLogger("test_specific_qt")
        assert qt_handler in target_logger.handlers

        # Настраиваем через chutils: логгер не должен завершиться досрочно без хэндлеров
        ch_logger = setup_logger("test_specific_qt", file_logging=False)
        assert getattr(ch_logger, "_chutils_configured", False) is True
        # Должен присутствовать и qt_handler, и консольный хэндлер chutils
        assert qt_handler in ch_logger.handlers
        assert len(ch_logger.handlers) >= 2

        remove_qt_logging(qt_handler, logger_name="test_specific_qt")

    clear_global_handlers()
