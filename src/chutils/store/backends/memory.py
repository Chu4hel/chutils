"""
Потокобезопасный In-Memory бэкенд для chutils.store.
"""
from __future__ import annotations

import threading
import time
from typing import Any

from .base import BaseStoreBackend


class MemoryStore(BaseStoreBackend):
    """Потокобезопасный in-memory бэкенд хранилища с поддержкой TTL."""

    def __init__(self) -> None:
        self._store: dict[str, tuple[Any, float | None]] = {}
        self._lock = threading.RLock()

    def _is_expired(self, expires_at: float | None) -> bool:
        if expires_at is None:
            return False
        return time.time() > expires_at

    def get(self, key: str, default: Any = None) -> Any:
        """Извлекает значение по ключу (синхронно).

        Args:
            key: Ключ записи.
            default: Значение по умолчанию, если ключ не найден или просрочен.

        Returns:
            Сохраненное значение или default.
        """
        with self._lock:
            if key not in self._store:
                return default
            val, expires_at = self._store[key]
            if self._is_expired(expires_at):
                del self._store[key]
                return default
            return val

    def set(self, key: str, value: Any, ttl: int | float | None = None) -> bool:
        """Сохраняет значение по ключу с опциональным TTL (синхронно).

        Args:
            key: Ключ записи.
            value: Сохраняемое значение.
            ttl: Время жизни записи в секундах.

        Returns:
            True, если запись успешно сохранена.
        """
        expires_at = (time.time() + ttl) if ttl is not None else None
        with self._lock:
            self._store[key] = (value, expires_at)
        return True

    def delete(self, key: str) -> bool:
        """Удаляет запись по ключу (синхронно).

        Args:
            key: Ключ записи.

        Returns:
            True, если ключ существовал и был удален.
        """
        with self._lock:
            if key in self._store:
                del self._store[key]
                return True
            return False

    def exists(self, key: str) -> bool:
        """Проверяет существование ключа (синхронно).

        Args:
            key: Ключ записи.

        Returns:
            True, если ключ существует и не просрочен.
        """
        with self._lock:
            if key not in self._store:
                return False
            _, expires_at = self._store[key]
            if self._is_expired(expires_at):
                del self._store[key]
                return False
            return True

    def clear(self) -> bool:
        """Полностью очищает хранилище (синхронно).

        Returns:
            True при успешной очистке.
        """
        with self._lock:
            self._store.clear()
        return True

    async def aget(self, key: str, default: Any = None) -> Any:
        """Извлекает значение по ключу (асинхронно).

        Args:
            key: Ключ записи.
            default: Значение по умолчанию, если ключ не найден или просрочен.

        Returns:
            Сохраненное значение или default.
        """
        return self.get(key, default=default)

    async def aset(self, key: str, value: Any, ttl: int | float | None = None) -> bool:
        """Сохраняет значение по ключу (асинхронно).

        Args:
            key: Ключ записи.
            value: Сохраняемое значение.
            ttl: Время жизни записи в секундах.

        Returns:
            True, если запись успешно сохранена.
        """
        return self.set(key, value, ttl=ttl)

    async def adelete(self, key: str) -> bool:
        """Удаляет запись по ключу (асинхронно).

        Args:
            key: Ключ записи.

        Returns:
            True, если ключ существовал и был удален.
        """
        return self.delete(key)

    async def aexists(self, key: str) -> bool:
        """Проверяет существование ключа (асинхронно).

        Args:
            key: Ключ записи.

        Returns:
            True, если ключ существует и не просрочен.
        """
        return self.exists(key)

    async def aclear(self) -> bool:
        """Полностью очищает хранилище (асинхронно).

        Returns:
            True при успешной очистке.
        """
        return self.clear()
