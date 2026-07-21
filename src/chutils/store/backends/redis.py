"""
Redis бэкенд для chutils.store.
"""
from __future__ import annotations

import importlib.util
import sys
from typing import Any

from chutils.exceptions import OptionalDependencyError
from .base import BaseStoreBackend


def is_redis_available() -> bool:
    """Проверяет доступность библиотеки redis в окружении.

    Returns:
        True, если пакет redis установлен.
    """
    if "redis" in sys.modules:
        return True
    try:
        return importlib.util.find_spec("redis") is not None
    except Exception:
        return False


class RedisStore(BaseStoreBackend):
    """Бэкенд хранилища на базе Redis (требует опционального пакета redis)."""

    def __init__(self, url: str = "redis://localhost:6379/0", **kwargs: Any) -> None:
        self._url = url
        self._kwargs = kwargs
        self._sync_client: Any = None
        self._async_client: Any = None

    def _ensure_redis(self) -> None:
        if not is_redis_available():
            raise OptionalDependencyError(
                "Пакет 'redis' не установлен.",
                dependency="redis",
                hint="Установите его через: pip install redis или uv add redis",
            )

    def _get_sync_client(self) -> Any:
        self._ensure_redis()
        if self._sync_client is None:
            import redis

            self._sync_client = redis.Redis.from_url(self._url, **self._kwargs)
        return self._sync_client

    def _get_async_client(self) -> Any:
        self._ensure_redis()
        if self._async_client is None:
            import redis.asyncio as aioredis

            self._async_client = aioredis.Redis.from_url(self._url, **self._kwargs)
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
        ex = int(ttl) if ttl is not None else None
        res = client.set(key, value, ex=ex)
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
        return int(res) > 0

    def exists(self, key: str) -> bool:
        """Проверяет существование ключа (синхронно).

        Args:
            key: Ключ записи.

        Returns:
            True, если ключ существует.
        """
        client = self._get_sync_client()
        res = client.exists(key)
        return int(res) > 0

    def clear(self) -> bool:
        """Очищает базу данных (синхронно).

        Returns:
            True при успешной очистке.
        """
        client = self._get_sync_client()
        res = client.flushdb()
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
        val = await client.get(key)
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
        ex = int(ttl) if ttl is not None else None
        res = await client.set(key, value, ex=ex)
        return bool(res)

    async def adelete(self, key: str) -> bool:
        """Удаляет запись по ключу (асинхронно).

        Args:
            key: Ключ записи.

        Returns:
            True, если ключ существовал и был удален.
        """
        client = self._get_async_client()
        res = await client.delete(key)
        return int(res) > 0

    async def aexists(self, key: str) -> bool:
        """Проверяет существование ключа (асинхронно).

        Args:
            key: Ключ записи.

        Returns:
            True, если ключ существует.
        """
        client = self._get_async_client()
        res = await client.exists(key)
        return int(res) > 0

    async def aclear(self) -> bool:
        """Очищает базу данных (асинхронно).

        Returns:
            True при успешной очистке.
        """
        client = self._get_async_client()
        res = await client.flushdb()
        return bool(res)
