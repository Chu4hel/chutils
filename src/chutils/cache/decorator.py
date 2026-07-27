import functools
import inspect
from collections.abc import Callable
from typing import Any

from .in_memory import InMemoryCacheBackend
from .utils import generate_cache_key, LockManager, AsyncLockManager

# Экземпляры по умолчанию
_default_backend: InMemoryCacheBackend[Any] = InMemoryCacheBackend()
_sync_lock_manager = LockManager()
_async_lock_manager = AsyncLockManager()


def cache_with_ttl(
        ttl: int = 60,
        key_prefix: str = "",
        sliding: bool = True,
        backend: InMemoryCacheBackend[Any] | None = None,
        tags: list[str] | Callable[..., list[str] | str] | None = None
) -> Callable[..., Any]:
    """
    Декоратор для кэширования результатов выполнения функций с поддержкой TTL.

    Декорированная функция получает дополнительные методы управления кэшем:
    * `invalidate(*args, **kwargs)` / `ainvalidate(*args, **kwargs)` — удаляет запись из кэша для указанных аргументов.
    * `invalidate_all()` / `ainvalidate_all()` — полностью очищает все записи этой функции.
    * `invalidate_tag(tag)` / `ainvalidate_tag(tag)` — сбрасывает все записи кэша, помеченные данным тегом.

    Args:
        ttl (int): Время жизни закэшированного значения в секундах. По умолчанию 60.
        key_prefix (str): Префикс для ключа кэша.
        sliding (bool): Если True, TTL продлевается при каждом успешном чтении из кэша.
        backend: Инстанс бэкенда для хранения (по умолчанию InMemoryCacheBackend).
        tags: Статические теги (list[str]) или вызываемый объект (callable), принимающий те же
              аргументы, что и декорируемая функция, и генерирующий тег или список тегов.

    Returns:
        Callable: Обернутая функция со встроенными методами инвалидации.
    """
    cache: InMemoryCacheBackend[Any] = backend or _default_backend

    def _resolve_tags(args: tuple[Any, ...], kwargs: dict[str, Any]) -> list[str] | None:
        if not tags:
            return None
        if callable(tags):
            try:
                res = tags(*args, **kwargs)
            except Exception:
                return None
            if isinstance(res, str):
                return [res]
            elif isinstance(res, (list, tuple, set)):
                return [str(x) for x in res]
            elif res is None:
                return None
            return [str(res)]
        elif isinstance(tags, (list, tuple, set)):
            return [str(x) for x in tags]
        elif isinstance(tags, str):
            return [tags]
        return [str(tags)]

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        func_name = f"{func.__module__}.{func.__name__}"
        is_async = inspect.iscoroutinefunction(func)
        generated_keys: set[str] = set()

        if is_async:
            @functools.wraps(func)
            async def wrapper(*args: Any, **kwargs: Any) -> Any:
                key = generate_cache_key(func_name, args, kwargs, prefix=key_prefix)
                generated_keys.add(key)
                resolved_tags = _resolve_tags(args, kwargs)

                # 1. Пробуем получить из кэша
                value = await cache.aget(key)
                if value is not None:
                    if sliding:
                        await cache.aset(key, value, ttl=ttl, tags=resolved_tags)
                    return value

                # 2. Защита от Stampede (асинхронная блокировка на ключ)
                lock = _async_lock_manager.get_lock(key)
                async with lock:
                    # Double-checked locking
                    value = await cache.aget(key)
                    if value is not None:
                        return value

                    # 3. Вычисляем значение
                    result = await func(*args, **kwargs)

                    # 4. Сохраняем в кэш
                    await cache.aset(key, result, ttl=ttl, tags=resolved_tags)
                    return result
        else:
            @functools.wraps(func)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                key = generate_cache_key(func_name, args, kwargs, prefix=key_prefix)
                generated_keys.add(key)
                resolved_tags = _resolve_tags(args, kwargs)

                # 1. Пробуем получить из кэша
                value = cache.get(key)
                if value is not None:
                    if sliding:
                        cache.set(key, value, ttl=ttl, tags=resolved_tags)
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
                    cache.set(key, result, ttl=ttl, tags=resolved_tags)
                    return result

        # Внедрение методов инвалидации
        def invalidate(*args: Any, **kwargs: Any) -> None:
            key = generate_cache_key(func_name, args, kwargs, prefix=key_prefix)
            cache.delete(key)
            generated_keys.discard(key)

        async def ainvalidate(*args: Any, **kwargs: Any) -> None:
            key = generate_cache_key(func_name, args, kwargs, prefix=key_prefix)
            await cache.adelete(key)
            generated_keys.discard(key)

        def invalidate_all() -> None:
            for key in list(generated_keys):
                cache.delete(key)
            generated_keys.clear()

        async def ainvalidate_all() -> None:
            for key in list(generated_keys):
                await cache.adelete(key)
            generated_keys.clear()

        def invalidate_tag(tag: str) -> None:
            cache.invalidate_tag(tag)

        async def ainvalidate_tag(tag: str) -> None:
            await cache.ainvalidate_tag(tag)

        wrapper.invalidate = invalidate  # type: ignore
        wrapper.ainvalidate = ainvalidate  # type: ignore
        wrapper.invalidate_all = invalidate_all  # type: ignore
        wrapper.ainvalidate_all = ainvalidate_all  # type: ignore
        wrapper.invalidate_tag = invalidate_tag  # type: ignore
        wrapper.ainvalidate_tag = ainvalidate_tag  # type: ignore

        return wrapper

    return decorator

    return decorator
