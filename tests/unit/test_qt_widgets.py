"""
Тесты для базовых виджетов Qt (src/chutils/qt/widgets.py).
"""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from chutils.exceptions import OptionalDependencyError
import chutils.qt.shim as shim


def test_widgets_without_qt() -> None:
    """Проверяет выбрасывание OptionalDependencyError при отсутствии Qt."""
    err = OptionalDependencyError("Библиотека PyQt6 или PySide6 не установлена.", dependency="qt")
    with patch.object(shim, "QT_BINDING", None), patch("chutils.qt.widgets.require_qt", side_effect=err):
        from chutils.qt.widgets import BaseDialog, BaseMainWindow
        with pytest.raises(OptionalDependencyError):
            BaseMainWindow()
        with pytest.raises(OptionalDependencyError):
            BaseDialog()



def test_base_main_window_lifecycle() -> None:
    """Проверяет логирование жизненного цикла BaseMainWindow и работу с геометрией."""
    mock_settings = MagicMock()
    mock_settings.value.return_value = b"saved_geometry"
    mock_qtcore = MagicMock()
    mock_qtcore.QSettings.return_value = mock_settings

    class FakeMainWindow:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        def restoreGeometry(self, *args: Any, **kwargs: Any) -> Any:
            pass

        def saveGeometry(self, *args: Any, **kwargs: Any) -> Any:
            pass

        def showEvent(self, event: Any) -> None:
            pass

        def closeEvent(self, event: Any) -> None:
            pass

    mock_qtwidgets = MagicMock()
    mock_qtwidgets.QMainWindow = FakeMainWindow

    with (
        patch.object(shim, "QT_BINDING", "PyQt6"),
        patch.object(shim, "require_qt", return_value=None),
        patch.object(shim, "QtWidgets", mock_qtwidgets),
        patch.object(shim, "QtCore", mock_qtcore),
        patch("chutils.qt.widgets.require_qt", return_value=None),
        patch("chutils.qt.widgets.QtCore", mock_qtcore),
    ):
        import importlib
        import chutils.qt.widgets
        importlib.reload(chutils.qt.widgets)
        from chutils.qt.widgets import BaseMainWindow

        window = BaseMainWindow()
        assert window.logger.name == "BaseMainWindow"
        window.saveGeometry = MagicMock(return_value=b"geometry_bytes")
        window.restoreGeometry = MagicMock()

        mock_event = MagicMock()
        window.showEvent(mock_event)
        window.restore_geometry_settings()
        window.restoreGeometry.assert_called_once_with(b"saved_geometry")

        window.closeEvent(mock_event)
        mock_settings.setValue.assert_called_once_with("geometry", b"geometry_bytes")


def test_base_dialog_lifecycle() -> None:
    """Проверяет логирование жизненного цикла BaseDialog."""
    class FakeDialog:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        def showEvent(self, event: Any) -> None:
            pass

        def closeEvent(self, event: Any) -> None:
            pass

    mock_qtwidgets = MagicMock()
    mock_qtwidgets.QDialog = FakeDialog

    with (
        patch.object(shim, "QT_BINDING", "PyQt6"),
        patch.object(shim, "require_qt", return_value=None),
        patch.object(shim, "QtWidgets", mock_qtwidgets),
        patch("chutils.qt.widgets.require_qt", return_value=None),
    ):
        import importlib
        import chutils.qt.widgets
        importlib.reload(chutils.qt.widgets)
        from chutils.qt.widgets import BaseDialog

        dialog = BaseDialog()
        assert dialog.logger.name == "BaseDialog"

        mock_event = MagicMock()
        dialog.showEvent(mock_event)
        dialog.closeEvent(mock_event)






