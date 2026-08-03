"""Тесты сбора Prometheus-метрических показателей очередей задач."""

import pytest
from chutils import metrics
from chutils.scraping.concurrency.metrics import QueueMetricsCollector
from chutils.scraping.concurrency.models import ScrapingTask
from chutils.scraping.concurrency.queues import InMemoryTaskQueue, PersistentTaskQueue


def test_queue_metrics_collector():
    collector = QueueMetricsCollector("test_q", "in_memory", enabled=True)
    collector.set_pending_size(10)
    collector.inc_tasks_processed("completed")
    collector.observe_execution_duration(1.23, "completed")
    collector.set_active_workers(4)

    # Выключенный коллектор не вызывает ошибок
    disabled_collector = QueueMetricsCollector("disabled_q", "in_memory", enabled=False)
    disabled_collector.set_pending_size(5)
    disabled_collector.inc_tasks_processed("failed")


@pytest.mark.asyncio
async def test_in_memory_queue_metrics():
    queue = InMemoryTaskQueue(name="test_mem", enable_metrics=True)
    assert await queue.size() == 0

    task = ScrapingTask(url="https://example.com/1")
    added = await queue.push(task)
    assert added is True
    assert await queue.size() == 1

    popped = await queue.pop()
    assert popped is not None
    assert popped.url == "https://example.com/1"
    assert await queue.size() == 0


@pytest.mark.asyncio
async def test_persistent_queue_metrics(tmp_path):
    db_file = tmp_path / "metrics_test.db"
    queue = PersistentTaskQueue(db_path=db_file, name="test_sqlite", enable_metrics=True)

    task = ScrapingTask(url="https://example.com/2")
    await queue.push(task)
    assert await queue.size() == 1

    popped = await queue.pop()
    assert popped is not None
    assert popped.url == "https://example.com/2"

    await queue.close()
