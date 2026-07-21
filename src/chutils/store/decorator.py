"""
Декоратор кэширования на базе StoreManager (chutils.store.decorator).
"""
from __future__ import annotations

import asyncio
import functools
from collections.abc import Callable
from typing import Any

from .manager import StoreManager

_default_store = StoreManager()


def _make_key(prefix: str, func: Callable[..., Any], args: tuple[Any, ...], kwargs: dict[str, Any]) -> str:
    func_name = getattr(func, "__qualname__", func.__name__)
    raw_args = f"{args}:{sorted(kwargs.items())}"
    return f"{prefix}{func_name}:{raw_args}"


def store_cache(
    store: StoreManager | None = None,
    ttl: int | float = 60,
    key_prefix: str = "cache:",
) -> Callable[..., Any]:
    """Декоратор для кэширования результатов вызова функций через StoreManager.

    Args:
        store: Экземпляр StoreManager (по умолчанию локальный in-memory StoreManager).
        ttl: Время жизни кэша в секундах.
        key_prefix: Префикс ключей кэша.

    Returns:
        Обернутая функция с методами инвалидации.
    """
    target_store = store or _default_store

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                cache_key = _make_key(key_prefix, func, args, kwargs)
                if await target_store.aexists(cache_key):
                    return await target_store.aget(cache_key)
                result = await func(*args, **kwargs)
                await target_store.aset(cache_key, result, ttl=ttl)
                return result

            async def ainvalidate(*args: Any, **kwargs: Any) -> bool:
                cache_key = _make_key(key_prefix, func, args, kwargs)
                return await target_store.adelete(cache_key)

            async def aclear() -> bool:
                return await target_store.aclear()

            async_wrapper.ainvalidate = ainvalidate  # type: ignore[attr-defined]
            async_wrapper.aclear = aclear  # type: ignore[attr-defined]
            return async_wrapper

        else:

            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                cache_key = _make_key(key_prefix, func, args, kwargs)
                if target_store.exists(cache_key):
                    return target_store.get(cache_key)
                result = func(*args, **kwargs)
                target_store.set(cache_key, result, ttl=ttl)
                return result

            def invalidate(*args: Any, **kwargs: Any) -> bool:
                cache_key = _make_key(key_prefix, func, args, kwargs)
                return target_store.delete(cache_key)

            def clear() -> bool:
                return target_store.clear()

            sync_wrapper.invalidate = invalidate  # type: ignore[attr-defined]
            sync_wrapper.clear = clear  # type: ignore[attr-defined]
            return sync_wrapper

    return decorator
