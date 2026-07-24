"""
Тесты для WorkerPool.
"""

import asyncio

import pytest

from chutils.scraping.concurrency.limiter import DomainRateLimiter
from chutils.scraping.concurrency.models import ScrapingTask
from chutils.scraping.concurrency.pool import WorkerPool
from chutils.scraping.concurrency.queues import InMemoryTaskQueue


@pytest.mark.asyncio
async def test_worker_pool_async_handler() -> None:
    """Проверяет обработку задач воркерами с асинхронной функцией-обработчиком."""
    queue = InMemoryTaskQueue()
    processed: list[str] = []

    async def sample_handler(task: ScrapingTask) -> None:
        await asyncio.sleep(0.01)
        processed.append(task.url)

    limiter = DomainRateLimiter(default_delay=0.01)
    pool = WorkerPool(queue=queue, handler=sample_handler, limiter=limiter, max_workers=3)

    await queue.push(ScrapingTask(url="https://site1.com/p1"))
    await queue.push(ScrapingTask(url="https://site2.com/p2"))
    await queue.push(ScrapingTask(url="https://site3.com/p3"))

    await pool.run_until_complete()

    assert len(processed) == 3
    assert set(processed) == {
        "https://site1.com/p1",
        "https://site2.com/p2",
        "https://site3.com/p3",
    }


@pytest.mark.asyncio
async def test_worker_pool_sync_handler() -> None:
    """Проверяет обработку задач воркерами с синхронной функцией-обработчиком."""
    queue = InMemoryTaskQueue()
    processed: list[str] = []

    def sync_handler(task: ScrapingTask) -> None:
        processed.append(task.url)

    pool = WorkerPool(queue=queue, handler=sync_handler, max_workers=2)

    await queue.push(ScrapingTask(url="https://sync.com/1"))
    await queue.push(ScrapingTask(url="https://sync.com/2"))

    await pool.run_until_complete()

    assert len(processed) == 2
