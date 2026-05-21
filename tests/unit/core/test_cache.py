import asyncio
import threading
import time

import pytest

from chutils.cache import InMemoryCacheBackend, cache_with_ttl
from chutils.cache.utils import generate_cache_key


def test_key_generation():
    """Тест детерминированной генерации ключей."""
    k1 = generate_cache_key("test.func", (1, 2), {"a": 3})
    k2 = generate_cache_key("test.func", (1, 2), {"a": 3})
    k3 = generate_cache_key("test.func", (1, 2), {"a": 4})

    assert k1 == k2
    assert k1 != k3
    assert k1.startswith("cache:")


def test_in_memory_backend_basic():
    """Базовые операции InMemoryCacheBackend."""
    backend = InMemoryCacheBackend()

    backend.set("key1", "val1", ttl=10)
    assert backend.get("key1") == "val1"
    assert backend.exists("key1") is True

    backend.delete("key1")
    assert backend.get("key1") is None
    assert backend.exists("key1") is False


def test_in_memory_backend_ttl():
    """Проверка истечения TTL."""
    backend = InMemoryCacheBackend()
    backend.set("key1", "val1", ttl=0.1)
    assert backend.get("key1") == "val1"

    time.sleep(0.2)
    assert backend.get("key1") is None
    assert backend.exists("key1") is False


def test_sync_decorator():
    """Тест синхронного декоратора."""
    call_count = 0
    backend = InMemoryCacheBackend()

    @cache_with_ttl(ttl=10, backend=backend)
    def heavy_func(x):
        nonlocal call_count
        call_count += 1
        return x * 2

    assert heavy_func(5) == 10
    assert heavy_func(5) == 10
    assert call_count == 1

    assert heavy_func(6) == 12
    assert call_count == 2


@pytest.mark.asyncio
async def test_async_decorator():
    """Тест асинхронного декоратора."""
    call_count = 0
    backend = InMemoryCacheBackend()

    @cache_with_ttl(ttl=10, backend=backend)
    async def heavy_async_func(x):
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.01)
        return x * 2

    assert await heavy_async_func(5) == 10
    assert await heavy_async_func(5) == 10
    assert call_count == 1


def test_sliding_ttl():
    """Тест продления TTL (sliding)."""
    backend = InMemoryCacheBackend()
    ttl = 2

    @cache_with_ttl(ttl=ttl, sliding=True, backend=backend)
    def func_sliding(x):
        return x

    # Определяем ключ так же, как декоратор
    func_name = f"{func_sliding.__module__}.func_sliding"
    key = generate_cache_key(func_name, (1,), {}, prefix="")

    func_sliding(1)
    assert backend.exists(key) is True

    time.sleep(1.1)
    # Обращение продлевает TTL еще на 2 сек
    func_sliding(1)

    time.sleep(1.1)
    # Прошло 2.2 сек с начала. Без sliding ключ бы умер через 2 сек.
    # Но так как был вызов на 1.1 сек, он должен жить до 3.1 сек.
    assert backend.exists(key) is True


def test_sync_stampede_protection():
    """Тест защиты от stampede в синхронном режиме."""
    call_count = 0
    backend = InMemoryCacheBackend()

    @cache_with_ttl(ttl=10, backend=backend)
    def func_sync_stampede():
        nonlocal call_count
        time.sleep(0.1)
        call_count += 1
        return "ok"

    threads = []
    results = []

    def target():
        results.append(func_sync_stampede())

    for _ in range(5):
        t = threading.Thread(target=target)
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    assert all(r == "ok" for r in results)
    assert call_count == 1


@pytest.mark.asyncio
async def test_async_stampede_protection():
    """Тест защиты от stampede в асинхронном режиме."""
    call_count = 0
    backend = InMemoryCacheBackend()

    @cache_with_ttl(ttl=10, backend=backend)
    async def func_async_stampede():
        nonlocal call_count
        await asyncio.sleep(0.1)
        call_count += 1
        return "ok"

    results = await asyncio.gather(*[func_async_stampede() for _ in range(5)])

    assert all(r == "ok" for r in results)
    assert call_count == 1
