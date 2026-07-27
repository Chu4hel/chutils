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
                import PyQt6.QtCore as _PyQt6_QtCore
                import PyQt6.QtGui as _PyQt6_QtGui
                import PyQt6.QtWidgets as _PyQt6_QtWidgets

                QT_BINDING = "PyQt6"
                QtCore = _PyQt6_QtCore
                QtGui = _PyQt6_QtGui
                QtWidgets = _PyQt6_QtWidgets

                Signal = getattr(_PyQt6_QtCore, "pyqtSignal", None)
                Slot = getattr(_PyQt6_QtCore, "pyqtSlot", None)
                Property = getattr(_PyQt6_QtCore, "pyqtProperty", None)
                QAction = getattr(_PyQt6_QtGui, "QAction", getattr(_PyQt6_QtWidgets, "QAction", None))
                return
            except ImportError:
                continue

        elif binding == "PySide6":
            try:
                import PySide6.QtCore as _PySide6_QtCore
                import PySide6.QtGui as _PySide6_QtGui
                import PySide6.QtWidgets as _PySide6_QtWidgets

                QT_BINDING = "PySide6"
                QtCore = _PySide6_QtCore
                QtGui = _PySide6_QtGui
                QtWidgets = _PySide6_QtWidgets

                Signal = getattr(_PySide6_QtCore, "Signal", None)
                Slot = getattr(_PySide6_QtCore, "Slot", None)
                Property = getattr(_PySide6_QtCore, "Property", None)
                QAction = getattr(_PySide6_QtGui, "QAction", getattr(_PySide6_QtWidgets, "QAction", None))
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
