"""
Тесты для очередей задач (InMemoryTaskQueue, PersistentTaskQueue, RedisTaskQueue).
"""

import json
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from chutils.exceptions import OptionalDependencyError
from chutils.scraping.concurrency.models import ScrapingTask
from chutils.scraping.concurrency.queues import (
    InMemoryTaskQueue,
    PersistentTaskQueue,
    RedisTaskQueue,
)


@pytest.mark.asyncio
async def test_in_memory_task_queue_priority_and_dedup() -> None:
    """Проверяет приоритеты и дедупликацию в InMemoryTaskQueue."""
    queue = InMemoryTaskQueue()

    task1 = ScrapingTask(url="https://example.com/1", priority=1)
    task2 = ScrapingTask(url="https://example.com/2", priority=10)
    task1_dup = ScrapingTask(url="https://example.com/1", priority=5)

    assert await queue.push(task1) is True
    assert await queue.push(task2) is True
    assert await queue.push(task1_dup) is False  # Дубликат

    assert await queue.size() == 2

    popped1 = await queue.pop()
    assert popped1 is not None
    assert popped1.url == "https://example.com/2"  # Высокий приоритет

    popped2 = await queue.pop()
    assert popped2 is not None
    assert popped2.url == "https://example.com/1"

    popped3 = await queue.pop()
    assert popped3 is None


@pytest.mark.asyncio
async def test_in_memory_task_queue_fail_retry() -> None:
    """Проверяет автоматический повтор сбойной задачи."""
    queue = InMemoryTaskQueue()
    task = ScrapingTask(url="https://example.com/fail", max_attempts=2)

    await queue.push(task)
    popped = await queue.pop()
    assert popped is not None

    await queue.fail(popped, "HTTP 500")
    assert await queue.size() == 1

    retry_task = await queue.pop()
    assert retry_task is not None
    assert retry_task.attempts == 1

    await queue.fail(retry_task, "HTTP 500")
    assert await queue.size() == 0  # Превышен лимит попыток

    # Проверка метода clear
    await queue.push(ScrapingTask(url="https://example.com/clear"))
    await queue.clear()
    assert await queue.size() == 0


@pytest.mark.asyncio
async def test_persistent_task_queue_sqlite() -> None:
    """Проверяет сохранение очереди в SQLite и восстановление состояния."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_queue.db")

        queue1 = PersistentTaskQueue(db_path=db_path)
        task1 = ScrapingTask(url="https://example.com/persisted", priority=5)
        assert await queue1.push(task1) is True
        await queue1.close()

        # Восстанавливаем состояние из того же файла
        queue2 = PersistentTaskQueue(db_path=db_path)
        assert await queue2.size() == 1

        popped = await queue2.pop()
        assert popped is not None
        assert popped.url == "https://example.com/persisted"
        await queue2.fail(popped, "DB Error")
        await queue2.clear()
        assert await queue2.size() == 0
        await queue2.close()


@pytest.mark.asyncio
async def test_persistent_task_queue_push_serialization_error() -> None:
    """Проверяет откат транзакции дедупликации при ошибке сериализации payload."""
    from datetime import datetime
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_leak.db")
        queue = PersistentTaskQueue(db_path=db_path)

        bad_task = ScrapingTask(url="https://e.com", dedup_key="key1", payload={"t": datetime.now()})
        with pytest.raises(TypeError):
            await queue.push(bad_task)

        good_task = ScrapingTask(url="https://e.com", dedup_key="key1", payload={"t": "2026-07-28"})
        result = await queue.push(good_task)
        assert result is True
        await queue.close()


def test_redis_task_queue_without_redis() -> None:
    """Проверяет исключение при отсутствии библиотеки redis."""
    with patch.dict("sys.modules", {"redis": None}):
        with pytest.raises(OptionalDependencyError) as exc_info:
            RedisTaskQueue()
        assert exc_info.value.context.get("dependency") == "redis"


@pytest.mark.asyncio
async def test_redis_task_queue_methods() -> None:
    """Проверяет методы push, pop, complete, fail, size и clear в RedisTaskQueue."""
    mock_redis = AsyncMock()
    mock_redis.sadd.return_value = True
    mock_redis.zpopmin.return_value = [(b"task_123", 0)]
    mock_redis.get.return_value = json.dumps({
        "url": "https://example.com/redis",
        "priority": 1,
        "payload": {},
        "attempts": 0,
        "max_attempts": 3,
        "task_id": "task_123",
        "dedup_key": "https://example.com/redis",
        "created_at": 1000.0,
        "last_error": None,
    })
    mock_redis.zcard.return_value = 1

    mock_module = MagicMock()
    mock_asyncio_module = MagicMock()
    mock_asyncio_module.from_url.return_value = mock_redis
    mock_module.asyncio = mock_asyncio_module

    with patch.dict("sys.modules", {"redis": mock_module, "redis.asyncio": mock_asyncio_module}):
        queue = RedisTaskQueue("redis://localhost:6379/0")

        task = ScrapingTask(url="https://example.com/redis", task_id="task_123")
        assert await queue.push(task) is True

        popped = await queue.pop()
        assert popped is not None
        assert popped.url == "https://example.com/redis"

        await queue.complete(popped)
        await queue.fail(popped, "Redis Error")
        assert await queue.size() == 1
        await queue.clear()
