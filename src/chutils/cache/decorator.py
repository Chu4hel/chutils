import asyncio
import functools
from typing import Callable, Optional

from .in_memory import InMemoryCacheBackend
from .utils import generate_cache_key, LockManager, AsyncLockManager
from ..typing import P, R

# Экземпляры по умолчанию
_default_backend: InMemoryCacheBackend[R] = InMemoryCacheBackend()  # type: ignore[valid-type]
_sync_lock_manager = LockManager()
_async_lock_manager = AsyncLockManager()


def cache_with_ttl(
        ttl: int = 60,
        key_prefix: str = "",
        sliding: bool = True,
        backend: Optional[InMemoryCacheBackend[R]] = None
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """
    Декоратор для кэширования результатов выполнения функций с поддержкой TTL.

    Args:
        ttl (int): Время жизни закэшированного значения в секундах. По умолчанию 60.
        key_prefix (str): Префикс для ключа кэша.
        sliding (bool): Если True, TTL продлевается при каждом успешном чтении из кэша.
        backend: Инстанс бэкенда для хранения (по умолчанию InMemoryCacheBackend).

    Returns:
        Callable: Обернутая функция.
    """
    cache: InMemoryCacheBackend[R] = backend or _default_backend  # type: ignore[assignment]

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        func_name = f"{func.__module__}.{func.__name__}"
        is_async = asyncio.iscoroutinefunction(func)

        if is_async:
            @functools.wraps(func)
            async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                key = generate_cache_key(func_name, args, kwargs, prefix=key_prefix)

                # 1. Пробуем получить из кэша
                value = await cache.aget(key)
                if value is not None:
                    if sliding:
                        await cache.aset(key, value, ttl=ttl)
                    return value

                # 2. Защита от Stampede (асинхронная блокировка на ключ)
                lock = _async_lock_manager.get_lock(key)
                async with lock:
                    # Double-checked locking
                    value = await cache.aget(key)
                    if value is not None:
                        return value

                    # 3. Вычисляем значение
                    result = await func(*args, **kwargs)  # type: ignore[no-any-return]

                    # 4. Сохраняем в кэш
                    await cache.aset(key, result, ttl=ttl)
                    return result
        else:
            @functools.wraps(func)
            def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                key = generate_cache_key(func_name, args, kwargs, prefix=key_prefix)

                # 1. Пробуем получить из кэша
                value = cache.get(key)
                if value is not None:
                    if sliding:
                        cache.set(key, value, ttl=ttl)
                    return value

                # 2. Защита от Stampede (синхронная блокировка на ключ)
                lock = _sync_lock_manager.get_lock(key)
                with lock:
                    # Double-checked locking
                    value = cache.get(key)
                    if value is not None:
                        return value

                    # 3. Вычисляем значение
                    result = func(*args, **kwargs)

                    # 4. Сохраняем в кэш
                    cache.set(key, result, ttl=ttl)
                    return result

        return wrapper  # type: ignore[return-value]

    return decorator
