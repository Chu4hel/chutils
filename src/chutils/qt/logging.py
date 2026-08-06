"""
Обработчик логов для Qt приложений (QtLogHandler).
"""

from __future__ import annotations

import logging  # chutils: ignore[ChutilsIntegrationRule]
from typing import Any

from .shim import QtCore, Signal, require_qt


class _QtLogEmitter(QtCore.QObject if QtCore is not None else object):  # type: ignore[misc]
    """Класс-эмиттер Qt сигналов для логгера."""

    if Signal is not None:
        message_emitted = Signal(str, int)  # formatted_message, levelno
    else:
        message_emitted = None


class QtLogHandler(logging.Handler):
    """Обработчик логов, транслирующий сообщения в Qt сигналы."""

    def __init__(self, level: int = logging.NOTSET) -> None:
        """Инициализирует обработчик логов.

        Args:
            level: Уровень логирования.
        """
        require_qt()
        super().__init__(level=level)
        self.emitter = _QtLogEmitter()

    def emit(self, record: logging.LogRecord) -> None:
        """Отправляет форматированное сообщение лога в сигнал Qt.

        Args:
            record: Запись лога.
        """
        try:
            msg = self.format(record)
            if self.emitter and self.emitter.message_emitted:
                self.emitter.message_emitted.emit(msg, record.levelno)
        except Exception:
            self.handleError(record)


def setup_qt_logging(
    widget: Any = None,
    level: int = logging.INFO,
    formatter: logging.Formatter | None = None,
    logger_name: str | None = None,
) -> QtLogHandler:
    """Быстро подключает вывод логов к Qt виджету или сигналу.

    Args:
        widget: Виджет Qt (QPlainTextEdit, QTextEdit, QStatusBar, QLabel) или слот-функция.
        level: Уровень логирования.
        formatter: Кастомный форматировщик логов.
        logger_name: Имя логгера (None для корневого логгера).

    Returns:
        Экземпляр QtLogHandler.
    """
    require_qt()
    handler = QtLogHandler(level=level)
    if formatter is not None:
        handler.setFormatter(formatter)
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))

    if widget is not None:
        if hasattr(widget, "appendPlainText"):
            handler.emitter.message_emitted.connect(lambda msg, lvl: widget.appendPlainText(msg))
        elif hasattr(widget, "append"):
            handler.emitter.message_emitted.connect(lambda msg, lvl: widget.append(msg))
        elif hasattr(widget, "showMessage"):
            handler.emitter.message_emitted.connect(lambda msg, lvl: widget.showMessage(msg))
        elif hasattr(widget, "setText"):
            handler.emitter.message_emitted.connect(lambda msg, lvl: widget.setText(msg))
        elif callable(widget):
            handler.emitter.message_emitted.connect(lambda msg, lvl: widget(msg))

    logger = logging.getLogger(logger_name)
    logger.addHandler(handler)
    return handler
