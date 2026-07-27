"""
Тесты для базовых виджетов Qt (src/chutils/qt/widgets.py).
"""

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

    with patch("chutils.qt.widgets.require_qt"):
        with patch("chutils.qt.widgets.QtCore", mock_qtcore):
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
    with patch("chutils.qt.widgets.require_qt"):
        from chutils.qt.widgets import BaseDialog

        dialog = BaseDialog()
        assert dialog.logger.name == "BaseDialog"

        mock_event = MagicMock()
        dialog.showEvent(mock_event)
        dialog.closeEvent(mock_event)
