"""
Тесты для слоя совместимости Qt (src/chutils/qt/shim.py).
"""

from unittest.mock import MagicMock, patch

import pytest

from chutils.exceptions import OptionalDependencyError
import chutils.qt.shim as shim


def test_require_qt_without_qt() -> None:
    """Проверяет выбрасывание OptionalDependencyError при отсутствии PyQt6/PySide6."""
    with patch.object(shim, "QT_BINDING", None):
        with pytest.raises(OptionalDependencyError) as exc_info:
            shim.require_qt()
        assert exc_info.value.context.get("dependency") == "qt"


def test_load_qt_pyqt6_mock() -> None:
    """Проверяет прозрачную загрузку PyQt6."""
    mock_qtcore = MagicMock()
    mock_qtgui = MagicMock()
    mock_qtwidgets = MagicMock()

    mock_qtcore.pyqtSignal = "pyqtSignal"
    mock_qtcore.pyqtSlot = "pyqtSlot"

    mock_pyqt6 = MagicMock()
    mock_pyqt6.QtCore = mock_qtcore
    mock_pyqt6.QtGui = mock_qtgui
    mock_pyqt6.QtWidgets = mock_qtwidgets

    modules = {
        "PyQt6": mock_pyqt6,
        "PyQt6.QtCore": mock_qtcore,
        "PyQt6.QtGui": mock_qtgui,
        "PyQt6.QtWidgets": mock_qtwidgets,
    }

    with patch.dict("sys.modules", modules):
        with patch.dict("os.environ", {"CHUTILS_QT_API": "pyqt6"}):
            shim._load_qt()
            assert shim.QT_BINDING == "PyQt6"
            assert shim.Signal == "pyqtSignal"


def test_load_qt_pyside6_mock() -> None:
    """Проверяет прозрачную загрузку PySide6."""
    mock_qtcore = MagicMock()
    mock_qtgui = MagicMock()
    mock_qtwidgets = MagicMock()

    mock_qtcore.Signal = "Signal"
    mock_qtcore.Slot = "Slot"

    mock_pyside6 = MagicMock()
    mock_pyside6.QtCore = mock_qtcore
    mock_pyside6.QtGui = mock_qtgui
    mock_pyside6.QtWidgets = mock_qtwidgets

    modules = {
        "PyQt6": None,
        "PySide6": mock_pyside6,
        "PySide6.QtCore": mock_qtcore,
        "PySide6.QtGui": mock_qtgui,
        "PySide6.QtWidgets": mock_qtwidgets,
    }

    with patch.dict("sys.modules", modules):
        with patch.dict("os.environ", {"CHUTILS_QT_API": "pyside6"}):
            shim._load_qt()
            assert shim.QT_BINDING == "PySide6"
            assert shim.Signal == "Signal"
