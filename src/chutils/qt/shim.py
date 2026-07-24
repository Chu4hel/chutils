"""
Слой совместимости для прозрачной работы с PyQt6 и PySide6.
"""

from __future__ import annotations

import os
from typing import Any

from chutils.exceptions import OptionalDependencyError

QT_BINDING: str | None = None
QtCore: Any = None
QtGui: Any = None
QtWidgets: Any = None

Signal: Any = None
Slot: Any = None
Property: Any = None
QAction: Any = None


def _load_qt() -> None:
    global QT_BINDING, QtCore, QtGui, QtWidgets, Signal, Slot, Property, QAction

    preferred = (os.getenv("CHUTILS_QT_API") or os.getenv("QT_API") or "").lower()

    bindings: list[str] = []
    if preferred in ("pyqt6", "pyqt"):
        bindings = ["PyQt6", "PySide6"]
    elif preferred in ("pyside6", "pyside"):
        bindings = ["PySide6", "PyQt6"]
    else:
        bindings = ["PyQt6", "PySide6"]

    for binding in bindings:
        if binding == "PyQt6":
            try:
                import PyQt6.QtCore as _QtCore
                import PyQt6.QtGui as _QtGui
                import PyQt6.QtWidgets as _QtWidgets

                QT_BINDING = "PyQt6"
                QtCore = _QtCore
                QtGui = _QtGui
                QtWidgets = _QtWidgets

                Signal = _QtCore.pyqtSignal
                Slot = _QtCore.pyqtSlot
                Property = _QtCore.pyqtProperty
                QAction = getattr(_QtGui, "QAction", getattr(_QtWidgets, "QAction", None))
                return
            except ImportError:
                continue

        elif binding == "PySide6":
            try:
                import PySide6.QtCore as _QtCore
                import PySide6.QtGui as _QtGui
                import PySide6.QtWidgets as _QtWidgets

                QT_BINDING = "PySide6"
                QtCore = _QtCore
                QtGui = _QtGui
                QtWidgets = _QtWidgets

                Signal = _QtCore.Signal
                Slot = _QtCore.Slot
                Property = _QtCore.Property
                QAction = getattr(_QtGui, "QAction", getattr(_QtWidgets, "QAction", None))
                return
            except ImportError:
                continue


_load_qt()


def require_qt() -> None:
    """Проверяет наличие установленной библиотеки Qt (PyQt6 или PySide6).

    Raises:
        OptionalDependencyError: Если ни PyQt6, ни PySide6 не установлены.
    """
    if QT_BINDING is None:
        raise OptionalDependencyError(
            "Библиотека PyQt6 или PySide6 не установлена.",
            dependency="qt",
            hint="Установите её с помощью 'pip install chutils[qt]'.",
        )
