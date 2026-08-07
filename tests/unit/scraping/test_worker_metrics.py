"""Unit-тесты метрик пула воркеров (WorkerPool)."""

import asyncio
import pytest
from chutils.scraping.concurrency.models import ScrapingTask
from chutils.scraping.concurrency.pool import WorkerPool
from chutils.scraping.concurrency.queues import InMemoryTaskQueue


@pytest.mark.asyncio
async def test_worker_pool_metrics():
    queue = InMemoryTaskQueue(name="worker_test_q", enable_metrics=True)
    await queue.push(ScrapingTask(url="https://test.com/1"))
    await queue.push(ScrapingTask(url="https://test.com/2", max_attempts=1))

    async def sample_handler(task: ScrapingTask) -> None:
        await asyncio.sleep(0.01)
        if "2" in task.url:
            raise ValueError("Failure simulation")

    pool = WorkerPool(queue=queue, handler=sample_handler, max_workers=2)
    await pool.run_until_complete()

    assert pool.completed_count == 1
    assert pool.failed_count == 1
