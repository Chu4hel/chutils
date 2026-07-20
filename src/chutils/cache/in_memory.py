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
        """Инициализирует бэкенд кэширования в памяти."""
        # Структура: {key: (value, expires_at)}
        self._cache: dict[str, tuple[T, float | None]] = {}
        self._lock = threading.Lock()
        self._async_lock: asyncio.Lock | None = None
        self._key_to_tags: dict[str, set[str]] = {}
        self._tag_to_keys: dict[str, set[str]] = {}

    def _get_async_lock(self) -> asyncio.Lock:
        if self._async_lock is None:
            self._async_lock = asyncio.Lock()
        return self._async_lock

    def _remove_key_associations(self, key: str) -> None:
        """Внутренний метод для удаления ассоциаций ключа с тегами."""
        tags = self._key_to_tags.pop(key, None)
        if tags:
            for tag in tags:
                if tag in self._tag_to_keys:
                    self._tag_to_keys[tag].discard(key)
                    if not self._tag_to_keys[tag]:
                        del self._tag_to_keys[tag]

    def get(self, key: str) -> T | None:
        """Получает значение по ключу. Если значение просрочено - удаляет его.

        Args:
            key: Ключ кэша.

        Returns:
            Значение из кэша или None, если оно отсутствует или просрочено.
        """
        with self._lock:
            return self._get_without_lock(key)

    def _get_without_lock(self, key: str) -> T | None:
        """Внутренний метод получения без блокировки (для использования внутри других методов)."""
        if key not in self._cache:
            return None

        value, expires_at = self._cache[key]
        if expires_at is not None and expires_at < time.time():
            del self._cache[key]
            self._remove_key_associations(key)
            return None

        return value

    def set(
        self,
        key: str,
        value: T,
        ttl: int | None = None,
        tags: list[str] | None = None,
    ) -> None:
        """Сохраняет значение с заданным TTL и тегами.

        Args:
            key: Ключ кэша.
            value: Сохраняемое значение.
            ttl: Время жизни записи в секундах.
            tags: Список тегов для связывания с ключом.
        """
        expires_at = time.time() + ttl if ttl is not None else None
        with self._lock:
            if key in self._cache:
                self._remove_key_associations(key)
            self._cache[key] = (value, expires_at)
            if tags:
                self._key_to_tags[key] = set(tags)
                for tag in tags:
                    self._tag_to_keys.setdefault(tag, set()).add(key)
            # При каждой вставке пробуем удалить несколько просроченных ключей
            self._lazy_evict()

    def delete(self, key: str) -> None:
        """Удаляет запись из кэша по ключу.

        Args:
            key: Ключ для удаления.
        """
        with self._lock:
            self._cache.pop(key, None)
            self._remove_key_associations(key)

    def exists(self, key: str) -> bool:
        """Проверить наличие ключа в кэше.

        Args:
            key: Ключ кэша.

        Returns:
            bool: True, если ключ существует и не просрочен.
        """
        with self._lock:
            return self._get_without_lock(key) is not None

    def clear(self) -> None:
        """Полная очистка."""
        with self._lock:
            self._cache.clear()
            self._key_to_tags.clear()
            self._tag_to_keys.clear()

    def invalidate_tag(self, tag: str) -> None:
        """Удаляет все ключи, связанные с указанным тегом.

        Args:
            tag: Тег для инвалидации.
        """
        with self._lock:
            keys = list(self._tag_to_keys.get(tag, set()))
            for key in keys:
                self._cache.pop(key, None)
                self._remove_key_associations(key)

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
                self._remove_key_associations(k)

    async def aget(self, key: str) -> T | None:
        """Асинхронно получает значение по ключу.

        Args:
            key: Ключ кэша.

        Returns:
            Значение из кэша или None, если оно отсутствует или просрочено.
        """
        async with self._get_async_lock():
            with self._lock:
                return self._get_without_lock(key)

    async def aset(
        self,
        key: str,
        value: T,
        ttl: int | None = None,
        tags: list[str] | None = None,
    ) -> None:
        """Асинхронно сохраняет значение с TTL и тегами.

        Args:
            key: Ключ кэша.
            value: Сохраняемое значение.
            ttl: Время жизни записи в секундах.
            tags: Список тегов для связывания с ключом.
        """
        expires_at = time.time() + ttl if ttl is not None else None
        async with self._get_async_lock():
            with self._lock:
                if key in self._cache:
                    self._remove_key_associations(key)
                self._cache[key] = (value, expires_at)
                if tags:
                    self._key_to_tags[key] = set(tags)
                    for tag in tags:
                        self._tag_to_keys.setdefault(tag, set()).add(key)
                self._lazy_evict()

    async def adelete(self, key: str) -> None:
        """Асинхронно удаляет запись из кэша по ключу.

        Args:
            key: Ключ для удаления.
        """
        async with self._get_async_lock():
            with self._lock:
                self._cache.pop(key, None)
                self._remove_key_associations(key)

    async def aexists(self, key: str) -> bool:
        """Асинхронно проверяет существование ключа в кэше.

        Args:
            key: Ключ для проверки.

        Returns:
            True, если ключ существует и не просрочен, иначе False.
        """
        async with self._get_async_lock():
            with self._lock:
                return self._get_without_lock(key) is not None

    async def aclear(self) -> None:
        """Асинхронная очистка кэша."""
        async with self._get_async_lock():
            with self._lock:
                self._cache.clear()
                self._key_to_tags.clear()
                self._tag_to_keys.clear()

    async def ainvalidate_tag(self, tag: str) -> None:
        """Асинхронно удаляет все ключи, связанные с указанным тегом.

        Args:
            tag: Тег для инвалидации.
        """
        async with self._get_async_lock():
            with self._lock:
                keys = list(self._tag_to_keys.get(tag, set()))
                for key in keys:
                    self._cache.pop(key, None)
                    self._remove_key_associations(key)
