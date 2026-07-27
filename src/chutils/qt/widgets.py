"""
Базовые шаблонные виджеты Qt (BaseMainWindow, BaseDialog) с интеграцией логирования и конфигов.
"""

from __future__ import annotations

import logging
from typing import Any

from .shim import QtCore, QtWidgets, require_qt


class BaseMainWindow(QtWidgets.QMainWindow if QtWidgets is not None else object):  # type: ignore[misc]
    """Базовое главное окно с встроенным логированием и сохранением геометрии."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Инициализирует базовое главное окно."""
        require_qt()
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.debug("Инициализация %s", self.__class__.__name__)

    def save_geometry_settings(self, key: str = "geometry") -> None:
        """Сохраняет размеры и положение окна в QSettings.

        Args:
            key: Ключ настройки.
        """
        if hasattr(self, "saveGeometry"):
            settings = QtCore.QSettings("chutils", self.__class__.__name__)
            settings.setValue(key, self.saveGeometry())

    def restore_geometry_settings(self, key: str = "geometry") -> None:
        """Восстанавливает размеры и положение окна из QSettings.

        Args:
            key: Ключ настройки.
        """
        if hasattr(self, "restoreGeometry"):
            settings = QtCore.QSettings("chutils", self.__class__.__name__)
            geom = settings.value(key)
            if geom is not None:
                self.restoreGeometry(geom)

    def showEvent(self, event: Any) -> None:
        """Обработчик события отображения окна.

        Args:
            event: QShowEvent.
        """
        self.logger.debug("Окно %s отображено", self.__class__.__name__)
        if hasattr(super(), "showEvent"):
            super().showEvent(event)

    def closeEvent(self, event: Any) -> None:
        """Обработчик события закрытия окна.

        Args:
            event: QCloseEvent.
        """
        self.logger.debug("Закрытие окна %s", self.__class__.__name__)
        self.save_geometry_settings()
        if hasattr(super(), "closeEvent"):
            super().closeEvent(event)


class BaseDialog(QtWidgets.QDialog if QtWidgets is not None else object):  # type: ignore[misc]
    """Базовый диалог с логированием жизненного цикла."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Инициализирует базовый диалог."""
        require_qt()
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.debug("Инициализация диалога %s", self.__class__.__name__)

    def showEvent(self, event: Any) -> None:
        """Обработчик события отображения диалога.

        Args:
            event: QShowEvent.
        """
        self.logger.debug("Диалог %s отображен", self.__class__.__name__)
        if hasattr(super(), "showEvent"):
            super().showEvent(event)

    def closeEvent(self, event: Any) -> None:
        """Обработчик события закрытия диалога.

        Args:
            event: QCloseEvent.
        """
        self.logger.debug("Закрытие диалога %s", self.__class__.__name__)
        if hasattr(super(), "closeEvent"):
            super().closeEvent(event)
