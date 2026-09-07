"""
Модуль chutils.qt: Интеграция PyQt6/PySide6 (логирование, асинхронность, базовые виджеты, типизированные сигналы).
"""

from .asyncio import QtAsyncWorker, async_to_qt, run_async_task
from .logging import (  # chutils: ignore[ChutilsIntegrationRule]
    QtLogHandler,
    setup_qt_logging,
)
from .shim import (
    QT_BINDING,
    Property,
    QAction,
    QtCore,
    QtGui,
    QtWidgets,
    Signal,
    Slot,
    require_qt,
)
from .signals import (
    AutoBindMixin,
    BoundTypedSignal,
    TypedSignal,
    bind_qt_signals,
    qt_slot,
)
from .widgets import BaseDialog, BaseMainWindow

__all__ = [
    "QT_BINDING",
    "AutoBindMixin",
    "BaseDialog",
    "BaseMainWindow",
    "BoundTypedSignal",
    "Property",
    "QAction",
    "QtAsyncWorker",
    "QtCore",
    "QtGui",
    "QtLogHandler",
    "QtWidgets",
    "Signal",
    "Slot",
    "TypedSignal",
    "async_to_qt",
    "bind_qt_signals",
    "qt_slot",
    "require_qt",
    "run_async_task",
    "setup_qt_logging",
]
