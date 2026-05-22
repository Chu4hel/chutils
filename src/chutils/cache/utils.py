import asyncio
import hashlib
import threading
import typing as t


def generate_cache_key(
        func_name: str,
        args: t.Tuple[t.Any, ...],
        kwargs: t.Dict[str, t.Any],
        prefix: str = ""
) -> str:
    """
    Генерирует детерминированный ключ кэша на основе имени функции и аргументов.
    """
    sorted_kwargs = sorted(kwargs.items())
    args_repr = f"args:{repr(args)}|kwargs:{repr(sorted_kwargs)}"
    base_str = f"{prefix}:{func_name}:{args_repr}"
    key_hash = hashlib.md5(base_str.encode('utf-8')).hexdigest()

    return f"cache:{key_hash}"


class LockManager:
    """Менеджер блокировок для синхронных вызовов."""

    def __init__(self) -> None:
        self._locks: t.Dict[str, threading.Lock] = {}
        self._global_lock = threading.Lock()

    def get_lock(self, key: str) -> threading.Lock:
        """Получить (или создать) блокировку для конкретного ключа."""
        with self._global_lock:
            if key not in self._locks:
                self._locks[key] = threading.Lock()
            return self._locks[key]


class AsyncLockManager:
    """Менеджер блокировок для асинхронных вызовов."""

    def __init__(self) -> None:
        self._locks: t.Dict[str, asyncio.Lock] = {}
        self._global_lock = threading.Lock()  # Используем threading.Lock для защиты словаря

    def get_lock(self, key: str) -> asyncio.Lock:
        """Получить (или создать) асинхронную блокировку для ключа."""
        with self._global_lock:
            if key not in self._locks:
                self._locks[key] = asyncio.Lock()
            return self._locks[key]
