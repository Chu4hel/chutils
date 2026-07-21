"""
Memcached бэкенд для chutils.store.
"""
from __future__ import annotations

import importlib.util
from typing import Any

from chutils.exceptions import OptionalDependencyError
from .base import BaseStoreBackend


def is_pymemcache_available() -> bool:
    """Проверяет доступность библиотеки pymemcache в окружении.

    Returns:
        True, если пакет pymemcache установлен.
    """
    return importlib.util.find_spec("pymemcache") is not None


def is_aiomemcache_available() -> bool:
    """Проверяет доступность библиотеки aiomemcache в окружении.

    Returns:
        True, если пакет aiomemcache установлен.
    """
    return importlib.util.find_spec("aiomemcache") is not None


class MemcachedStore(BaseStoreBackend):
    """Бэкенд хранилища на базе Memcached (требует опционального пакета pymemcache)."""

    def __init__(self, host: str = "127.0.0.1", port: int = 11211, **kwargs: Any) -> None:
        self._host = host
        self._port = port
        self._kwargs = kwargs
        self._sync_client: Any = None
        self._async_client: Any = None

    def _ensure_pymemcache(self) -> None:
        if not is_pymemcache_available():
            raise OptionalDependencyError(
                "Пакет 'pymemcache' не установлен.",
                dependency="pymemcache",
                hint="Установите его через: pip install pymemcache или uv add pymemcache",
            )

    def _get_sync_client(self) -> Any:
        self._ensure_pymemcache()
        if self._sync_client is None:
            from pymemcache.client.base import Client

            self._sync_client = Client((self._host, self._port), **self._kwargs)
        return self._sync_client

    def _get_async_client(self) -> Any:
        if not is_aiomemcache_available():
            raise OptionalDependencyError(
                "Пакет 'aiomemcache' не установлен.",
                dependency="aiomemcache",
                hint="Установите его через: pip install aiomemcache или uv add aiomemcache",
            )
        if self._async_client is None:
            import aiomemcache

            self._async_client = aiomemcache.Client(self._host, self._port, **self._kwargs)
        return self._async_client

    def get(self, key: str, default: Any = None) -> Any:
        """Извлекает значение по ключу (синхронно).

        Args:
            key: Ключ записи.
            default: Значение по умолчанию, если ключ не найден.

        Returns:
            Сохраненное значение или default.
        """
        client = self._get_sync_client()
        val = client.get(key)
        return default if val is None else val

    def set(self, key: str, value: Any, ttl: int | float | None = None) -> bool:
        """Сохраняет значение по ключу с опциональным TTL (синхронно).

        Args:
            key: Ключ записи.
            value: Сохраняемое значение.
            ttl: Время жизни записи в секундах.

        Returns:
            True, если запись успешно сохранена.
        """
        client = self._get_sync_client()
        expire = int(ttl) if ttl is not None else 0
        res = client.set(key, value, expire=expire)
        return bool(res)

    def delete(self, key: str) -> bool:
        """Удаляет запись по ключу (синхронно).

        Args:
            key: Ключ записи.

        Returns:
            True, если ключ существовал и был удален.
        """
        client = self._get_sync_client()
        res = client.delete(key)
        return bool(res)

    def exists(self, key: str) -> bool:
        """Проверяет существование ключа (синхронно).

        Args:
            key: Ключ записи.

        Returns:
            True, если ключ существует.
        """
        client = self._get_sync_client()
        val = client.get(key)
        return val is not None

    def clear(self) -> bool:
        """Очищает сервер Memcached (синхронно).

        Returns:
            True при успешной очистке.
        """
        client = self._get_sync_client()
        res = client.flush_all()
        return bool(res)

    async def aget(self, key: str, default: Any = None) -> Any:
        """Извлекает значение по ключу (асинхронно).

        Args:
            key: Ключ записи.
            default: Значение по умолчанию, если ключ не найден.

        Returns:
            Сохраненное значение или default.
        """
        client = self._get_async_client()
        val = await client.get(key.encode("utf-8"))
        return default if val is None else val

    async def aset(self, key: str, value: Any, ttl: int | float | None = None) -> bool:
        """Сохраняет значение по ключу (асинхронно).

        Args:
            key: Ключ записи.
            value: Сохраняемое значение.
            ttl: Время жизни записи в секундах.

        Returns:
            True, если запись успешно сохранена.
        """
        client = self._get_async_client()
        ex = int(ttl) if ttl is not None else 0
        val = value if isinstance(value, bytes) else str(value).encode("utf-8")
        res = await client.set(key.encode("utf-8"), val, exptime=ex)
        return bool(res)

    async def adelete(self, key: str) -> bool:
        """Удаляет запись по ключу (асинхронно).

        Args:
            key: Ключ записи.

        Returns:
            True, если ключ существовал и был удален.
        """
        client = self._get_async_client()
        res = await client.delete(key.encode("utf-8"))
        return bool(res)

    async def aexists(self, key: str) -> bool:
        """Проверяет существование ключа (асинхронно).

        Args:
            key: Ключ записи.

        Returns:
            True, если ключ существует.
        """
        val = await self.aget(key, default=None)
        return val is not None

    async def aclear(self) -> bool:
        """Очищает сервер Memcached (асинхронно).

        Returns:
            True при успешной очистке.
        """
        client = self._get_async_client()
        res = await client.flush_all()
        return bool(res)
