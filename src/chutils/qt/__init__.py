"""
Модуль chutils.qt: Интеграция PyQt6/PySide6 (логирование, асинхронность, базовые виджеты).
"""

from .asyncio import QtAsyncWorker, async_to_qt, run_async_task
from .logging import QtLogHandler, setup_qt_logging
from .shim import (
    Property,
    QAction,
    QT_BINDING,
    Signal,
    Slot,
    QtCore,
    QtGui,
    QtWidgets,
    require_qt,
)
from .widgets import BaseDialog, BaseMainWindow

__all__ = [
    "QT_BINDING",
    "QtCore",
    "QtGui",
    "QtWidgets",
    "Signal",
    "Slot",
    "Property",
    "QAction",
    "require_qt",
    "QtLogHandler",
    "setup_qt_logging",
    "QtAsyncWorker",
    "run_async_task",
    "async_to_qt",
    "BaseMainWindow",
    "BaseDialog",
]
