"""
Абстрактный базовый класс бэкендов Key-Value хранилища chutils.store.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseStoreBackend(ABC):
    """Абстрактный базовый класс для всех бэкендов Key-Value хранилищ."""

    @abstractmethod
    def get(self, key: str, default: Any = None) -> Any:
        """Извлекает значение по ключу (синхронно).

        Args:
            key: Ключ записи.
            default: Значение по умолчанию, если ключ не найден или просрочен.

        Returns:
            Сохраненное значение или default.
        """
        raise NotImplementedError

    @abstractmethod
    def set(self, key: str, value: Any, ttl: int | float | None = None) -> bool:
        """Сохраняет значение по ключу с опциональным TTL (синхронно).

        Args:
            key: Ключ записи.
            value: Сохраняемое значение.
            ttl: Время жизни записи в секундах.

        Returns:
            True, если запись успешно сохранена.
        """
        raise NotImplementedError

    @abstractmethod
    def delete(self, key: str) -> bool:
        """Удаляет запись по ключу (синхронно).

        Args:
            key: Ключ записи.

        Returns:
            True, если ключ существовал и был удален.
        """
        raise NotImplementedError

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Проверяет существование ключа (синхронно).

        Args:
            key: Ключ записи.

        Returns:
            True, если ключ существует и не просрочен.
        """
        raise NotImplementedError

    @abstractmethod
    def clear(self) -> bool:
        """Полностью очищает хранилище (синхронно).

        Returns:
            True при успешной очистке.
        """
        raise NotImplementedError

    @abstractmethod
    async def aget(self, key: str, default: Any = None) -> Any:
        """Извлекает значение по ключу (асинхронно).

        Args:
            key: Ключ записи.
            default: Значение по умолчанию, если ключ не найден или просрочен.

        Returns:
            Сохраненное значение или default.
        """
        raise NotImplementedError

    @abstractmethod
    async def aset(self, key: str, value: Any, ttl: int | float | None = None) -> bool:
        """Сохраняет значение по ключу с опциональным TTL (асинхронно).

        Args:
            key: Ключ записи.
            value: Сохраняемое значение.
            ttl: Время жизни записи в секундах.

        Returns:
            True, если запись успешно сохранена.
        """
        raise NotImplementedError

    @abstractmethod
    async def adelete(self, key: str) -> bool:
        """Удаляет запись по ключу (асинхронно).

        Args:
            key: Ключ записи.

        Returns:
            True, если ключ существовал и был удален.
        """
        raise NotImplementedError

    @abstractmethod
    async def aexists(self, key: str) -> bool:
        """Проверяет существование ключа (асинхронно).

        Args:
            key: Ключ записи.

        Returns:
            True, если ключ существует и не просрочен.
        """
        raise NotImplementedError

    @abstractmethod
    async def aclear(self) -> bool:
        """Полностью очищает хранилище (асинхронно).

        Returns:
            True при успешной очистке.
        """
        raise NotImplementedError
