import asyncio
import threading
import time
from typing import TypeVar

from .base import BaseCacheBackend

T = TypeVar("T")


class InMemoryCacheBackend(BaseCacheBackend[T]):
    """
    Реализация кэша в оперативной памяти на базе словаря.

    Поддерживает TTL, потокобезопасность и ленивую очистку просроченных записей.
    """

    def __init__(self) -> None:
        # Структура: {key: (value, expires_at)}
        self._cache: dict[str, tuple[T, float | None]] = {}
        self._lock = threading.Lock()
        self._async_lock: asyncio.Lock | None = None

    def _get_async_lock(self) -> asyncio.Lock:
        if self._async_lock is None:
            self._async_lock = asyncio.Lock()
        return self._async_lock

    def get(self, key: str) -> T | None:
        """Получить значение. Если просрочено - удаляет его."""
        with self._lock:
            return self._get_without_lock(key)

    def _get_without_lock(self, key: str) -> T | None:
        """Внутренний метод получения без блокировки (для использования внутри других методов)."""
        if key not in self._cache:
            return None

        value, expires_at = self._cache[key]
        if expires_at is not None and expires_at < time.time():
            del self._cache[key]
            return None

        return value

    def set(self, key: str, value: T, ttl: int | None = None) -> None:
        """Сохранить значение с TTL."""
        expires_at = time.time() + ttl if ttl is not None else None
        with self._lock:
            self._cache[key] = (value, expires_at)
            # При каждой вставке пробуем удалить несколько просроченных ключей
            self._lazy_evict()

    def delete(self, key: str) -> None:
        """Удалить ключ."""
        with self._lock:
            self._cache.pop(key, None)

    def exists(self, key: str) -> bool:
        """Проверить наличие ключа (удаляет, если просрочен)."""
        with self._lock:
            return self._get_without_lock(key) is not None

    def clear(self) -> None:
        """Полная очистка."""
        with self._lock:
            self._cache.clear()

    def _lazy_evict(self, limit: int = 5) -> None:
        """
        Ленивая очистка просроченных ключей.
        Проверяет ограниченное количество ключей, чтобы не блокировать поток надолго.
        """
        now = time.time()
        keys_to_check = list(self._cache.keys())[:limit]
        for k in keys_to_check:
            _, expires_at = self._cache[k]
            if expires_at is not None and expires_at < now:
                del self._cache[k]

    async def aget(self, key: str) -> T | None:
        """Асинхронное получение значения."""
        async with self._get_async_lock():
            with self._lock:
                return self._get_without_lock(key)

    async def aset(self, key: str, value: T, ttl: int | None = None) -> None:
        """Асинхронное сохранение значения."""
        expires_at = time.time() + ttl if ttl is not None else None
        async with self._get_async_lock():
            with self._lock:
                self._cache[key] = (value, expires_at)
                self._lazy_evict()

    async def adelete(self, key: str) -> None:
        """Асинхронное удаление значения."""
        async with self._get_async_lock():
            with self._lock:
                self._cache.pop(key, None)

    async def aexists(self, key: str) -> bool:
        """Асинхронная проверка наличия ключа."""
        async with self._get_async_lock():
            with self._lock:
                return self._get_without_lock(key) is not None

    async def aclear(self) -> None:
        """Асинхронная очистка кэша."""
        async with self._get_async_lock():
            with self._lock:
                self._cache.clear()
