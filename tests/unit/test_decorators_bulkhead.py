"""
Тесты для исключения BulkheadLimitExceeded и декораторов resilience.
"""
from __future__ import annotations

import asyncio
import threading
import time

import pytest

from chutils.decorators import semaphore, bulkhead
from chutils.exceptions import BulkheadLimitExceeded


def test_bulkhead_limit_exceeded_inheritance() -> None:
    """Проверяет корректность наследования и инициализации исключения BulkheadLimitExceeded."""
    from chutils.exceptions import ChutilsException

    exc = BulkheadLimitExceeded("Limit exceeded", hint="Try again later", resource="database")
    assert isinstance(exc, ChutilsException)
    assert exc.message == "Limit exceeded"
    assert exc.hint == "Try again later"
    assert exc.context == {"resource": "database"}
    assert "[Контекст: resource='database']" in str(exc)
    assert "СОВЕТ: Try again later" in str(exc)


def test_sync_semaphore() -> None:
    """Проверяет работу синхронного декоратора @semaphore."""
    active_calls = 0
    max_active = 0
    lock = threading.Lock()

    @semaphore(max_concurrent=2)
    def worker() -> None:
        nonlocal active_calls, max_active
        with lock:
            active_calls += 1
            if active_calls > max_active:
                max_active = active_calls
        time.sleep(0.05)
        with lock:
            active_calls -= 1

    # Запускаем 4 потока
    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Убеждаемся, что одновременно выполнялось не более 2 потоков
    assert max_active <= 2


def test_sync_semaphore_with_key() -> None:
    """Проверяет разделение семафоров по ключу."""
    active_calls: dict[str, int] = {"A": 0, "B": 0}
    max_active: dict[str, int] = {"A": 0, "B": 0}
    lock = threading.Lock()

    @semaphore(max_concurrent=1, key=lambda category: category)
    def worker(category: str) -> None:
        nonlocal active_calls, max_active
        with lock:
            active_calls[category] += 1
            if active_calls[category] > max_active[category]:
                max_active[category] = active_calls[category]
        time.sleep(0.05)
        with lock:
            active_calls[category] -= 1

    # Запускаем потоки для категории A и B параллельно.
    # Так как у них разные ключи, они не должны блокировать друг друга,
    # но внутри каждой категории макс. параллельность должна быть 1.
    threads = [
        threading.Thread(target=worker, args=("A",)),
        threading.Thread(target=worker, args=("A",)),
        threading.Thread(target=worker, args=("B",)),
        threading.Thread(target=worker, args=("B",)),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert max_active["A"] == 1
    assert max_active["B"] == 1


@pytest.mark.asyncio
async def test_async_semaphore() -> None:
    """Проверяет работу асинхронного декоратора @semaphore."""
    active_calls = 0
    max_active = 0

    @semaphore(max_concurrent=2)
    async def worker() -> None:
        nonlocal active_calls, max_active
        active_calls += 1
        if active_calls > max_active:
            max_active = active_calls
        await asyncio.sleep(0.05)
        active_calls -= 1

    # Запускаем 4 таски
    await asyncio.gather(worker(), worker(), worker(), worker())

    assert max_active <= 2


@pytest.mark.asyncio
async def test_async_semaphore_with_key() -> None:
    """Проверяет разделение асинхронных семафоров по ключу."""
    active_calls: dict[str, int] = {"A": 0, "B": 0}
    max_active: dict[str, int] = {"A": 0, "B": 0}

    @semaphore(max_concurrent=1, key=lambda category: category)
    async def worker(category: str) -> None:
        nonlocal active_calls, max_active
        active_calls[category] += 1
        if active_calls[category] > max_active[category]:
            max_active[category] = active_calls[category]
        await asyncio.sleep(0.05)
        active_calls[category] -= 1

    await asyncio.gather(
        worker("A"),
        worker("A"),
        worker("B"),
        worker("B"),
    )

    assert max_active["A"] == 1
    assert max_active["B"] == 1


def test_sync_bulkhead_fast_fail() -> None:
    """Проверяет Fast-Fail поведение @bulkhead при max_waiting=0."""

    @bulkhead(max_concurrent=1, max_waiting=0)
    def worker() -> None:
        time.sleep(0.05)

    t = threading.Thread(target=worker)
    t.start()
    time.sleep(0.01)

    with pytest.raises(BulkheadLimitExceeded):
        worker()

    t.join()


def test_sync_bulkhead_waiting_queue() -> None:
    """Проверяет работу очереди ожидания в синхронном @bulkhead."""

    @bulkhead(max_concurrent=1, max_waiting=1)
    def worker() -> None:
        time.sleep(0.05)

    t1 = threading.Thread(target=worker)
    t1.start()
    time.sleep(0.01)

    t2 = threading.Thread(target=worker)
    t2.start()
    time.sleep(0.01)

    with pytest.raises(BulkheadLimitExceeded):
        worker()

    t1.join()
    t2.join()


def test_sync_bulkhead_timeout() -> None:
    """Проверяет таймаут ожидания слота в синхронном @bulkhead."""

    @bulkhead(max_concurrent=1, max_waiting=1, timeout=0.02)
    def worker() -> None:
        time.sleep(0.06)

    t1 = threading.Thread(target=worker)
    t1.start()
    time.sleep(0.01)

    with pytest.raises(BulkheadLimitExceeded):
        worker()

    t1.join()


def test_sync_bulkhead_fallback() -> None:
    """Проверяет работу fallback в синхронном @bulkhead."""

    @bulkhead(max_concurrent=1, max_waiting=0, fallback="fallback_value")
    def worker1() -> str:
        time.sleep(0.05)
        return "ok"

    @bulkhead(max_concurrent=1, max_waiting=0, fallback=lambda x: f"fallback_{x}")
    def worker2(x: int) -> str:
        time.sleep(0.05)
        return "ok"

    t1 = threading.Thread(target=worker1)
    t1.start()
    time.sleep(0.01)
    assert worker1() == "fallback_value"
    t1.join()

    t2 = threading.Thread(target=worker2, args=(42,))
    t2.start()
    time.sleep(0.01)
    assert worker2(42) == "fallback_42"
    t2.join()


@pytest.mark.asyncio
async def test_async_bulkhead_fast_fail() -> None:
    """Проверяет Fast-Fail в асинхронном @bulkhead."""

    @bulkhead(max_concurrent=1, max_waiting=0)
    async def worker() -> None:
        await asyncio.sleep(0.05)

    task = asyncio.create_task(worker())
    await asyncio.sleep(0.01)

    with pytest.raises(BulkheadLimitExceeded):
        await worker()

    await task


@pytest.mark.asyncio
async def test_async_bulkhead_timeout_and_fallback() -> None:
    """Проверяет таймаут и fallback в асинхронном @bulkhead."""

    async def async_fallback(x: int) -> str:
        return f"async_{x}"

    @bulkhead(max_concurrent=1, max_waiting=1, timeout=0.01, fallback=async_fallback)
    async def worker(x: int) -> str:
        await asyncio.sleep(0.05)
        return "ok"

    task = asyncio.create_task(worker(1))
    await asyncio.sleep(0.005)

    res = await worker(2)
    assert res == "async_2"

    await task


def test_chutils_root_imports() -> None:
    """Проверяет импорт декораторов и исключений напрямую из корня библиотеки chutils."""
    import chutils
    
    assert hasattr(chutils, "semaphore")
    assert hasattr(chutils, "bulkhead")
    assert hasattr(chutils, "BulkheadLimitExceeded")
    
    assert chutils.semaphore is semaphore
    assert chutils.bulkhead is bulkhead
    assert chutils.BulkheadLimitExceeded is BulkheadLimitExceeded
