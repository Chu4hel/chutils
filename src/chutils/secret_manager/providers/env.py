from __future__ import annotations

import os

from . import _get_logger
from .base import SecretProvider


class EnvProvider(SecretProvider):
    """
    Провайдер для работы с переменными окружения ОС (os.environ).
    """

    def get(self, key: str, service_name: str) -> str | None:
        """Получает значение из переменных окружения ОС.

        Args:
            key: Имя запрашиваемого секрета.
            service_name: Имя сервиса/приложения.

        Returns:
            Значение секрета или None, если он не найден.
        """
        value = os.environ.get(key)  # chutils: ignore[ChutilsIntegrationRule]
        if value is not None:
            _get_logger().devdebug("Секрет '%s' найден в переменных окружения.", key)
        return value

    def set(self, key: str, value: str, service_name: str) -> bool:
        """EnvProvider не поддерживает сохранение.

        Args:
            key: Имя секрета.
            value: Значение секрета.
            service_name: Имя сервиса.

        Returns:
            Всегда False, так как запись не поддерживается.
        """
        _get_logger().warning("EnvProvider не поддерживает сохранение секретов.")
        return False

    def delete(self, key: str, service_name: str) -> bool:
        """EnvProvider не поддерживает удаление.

        Args:
            key: Имя секрета.
            service_name: Имя сервиса.

        Returns:
            Всегда False, так как удаление не поддерживается.
        """
        _get_logger().warning("EnvProvider не поддерживает удаление секретов.")
        return False
