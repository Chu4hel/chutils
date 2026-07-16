from __future__ import annotations

import os

from dotenv import load_dotenv

from . import _get_logger
from .base import SecretProvider
from ... import config


class DotEnvProvider(SecretProvider):
    """
    Провайдер для работы с .env файлами.
    Обеспечивает загрузку переменных окружения из файла при первом обращении.
    """

    def __init__(self, dotenv_path: str | None = None):
        """
        Инициализирует провайдер.

        Args:
            dotenv_path: Явный путь к .env файлу. Если не указан, ищется в корне проекта.
        """
        self.dotenv_path = dotenv_path
        self._loaded = False
        self._values: dict[str, str] = {}

    def _load_if_needed(self) -> None:
        """
        Загружает переменные из .env файла, если это еще не было сделано.
        """
        if self._loaded:
            return

        path = self.dotenv_path
        if not path:
            base_dir = config.get_base_dir()
            if base_dir:
                path = os.path.join(base_dir, '.env')

        if path and os.path.exists(path):
            load_dotenv(dotenv_path=path, override=False)
            _get_logger().debug("Найден и загружен .env файл: %s", path)

        # Кэшируем текущие переменные окружения
        self._values = dict(os.environ)
        self._loaded = True

    def get(self, key: str, service_name: str) -> str | None:
        """Получает значение из загруженных .env данных.

        Args:
            key: Имя запрашиваемого секрета.
            service_name: Имя сервиса/приложения.

        Returns:
            Значение секрета или None, если он не найден.
        """
        self._load_if_needed()
        value = self._values.get(key)
        if value is not None:
            _get_logger().devdebug("Секрет '%s' найден в .env файле.", key)
        return value

    def set(self, key: str, value: str, service_name: str) -> bool:
        """DotEnvProvider не поддерживает сохранение (доступен только для чтения).

        Args:
            key: Имя секрета.
            value: Значение секрета.
            service_name: Имя сервиса.

        Returns:
            Всегда False, так как запись не поддерживается.
        """
        _get_logger().warning("DotEnvProvider не поддерживает сохранение секретов.")
        return False

    def delete(self, key: str, service_name: str) -> bool:
        """DotEnvProvider не поддерживает удаление.

        Args:
            key: Имя секрета.
            service_name: Имя сервиса.

        Returns:
            Всегда False, так как удаление не поддерживается.
        """
        _get_logger().warning("DotEnvProvider не поддерживает удаление секретов.")
        return False
