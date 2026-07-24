"""
Реализации очередей задач: InMemoryTaskQueue, PersistentTaskQueue, RedisTaskQueue.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path
from typing import Any

from chutils.exceptions import OptionalDependencyError
from .base import BaseTaskQueue
from .models import ScrapingTask


class InMemoryTaskQueue(BaseTaskQueue):
    """Быстрая очередь задач в оперативной памяти."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._seen: set[str] = set()
        self._queue: list[ScrapingTask] = []
        self._failed_tasks: list[ScrapingTask] = []

    async def push(self, task: ScrapingTask) -> bool:
        """Добавляет задачу в оперативную очередь.

        Args:
            task: Задача для добавления.

        Returns:
            True, если задача успешно добавлена; False, если задача дедуплицирована.
        """
        async with self._lock:
            if task.dedup_key in self._seen:
                return False
            self._seen.add(task.dedup_key)
            self._queue.append(task)
            self._queue.sort(key=lambda t: (-t.priority, t.created_at))
            return True

    async def pop(self) -> ScrapingTask | None:
        """Извлекает задачу с наивысшим приоритетом из очереди.

        Returns:
            Экземпляр ScrapingTask или None, если очередь пуста.
        """
        async with self._lock:
            if not self._queue:
                return None
            return self._queue.pop(0)

    async def complete(self, task: ScrapingTask) -> None:
        """Помечает задачу как выполненную.

        Args:
            task: Выполненная задача.
        """
        pass

    async def fail(self, task: ScrapingTask, error: str) -> None:
        """Обрабатывает ошибку выполнения задачи.

        Args:
            task: Сбойная задача.
            error: Сообщение об ошибке.
        """
        async with self._lock:
            task.last_error = error
            task.attempts += 1
            if task.attempts < task.max_attempts:
                self._queue.append(task)
                self._queue.sort(key=lambda t: (-t.priority, t.created_at))
            else:
                self._failed_tasks.append(task)

    async def size(self) -> int:
        """Возвращает количество ожидающих задач в очереди.

        Returns:
            Размер очереди.
        """
        async with self._lock:
            return len(self._queue)

    async def clear(self) -> None:
        """Очищает очередь и сбрасывает историю дедупликации."""
        async with self._lock:
            self._queue.clear()
            self._seen.clear()
            self._failed_tasks.clear()


class PersistentTaskQueue(BaseTaskQueue):
    """Очередь задач с персистентным сохранением состояния в SQLite."""

    def __init__(self, db_path: str | Path = "scraping_queue.db") -> None:
        self.db_path = str(db_path)
        self._lock = asyncio.Lock()
        self._conn: sqlite3.Connection | None = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        if self._conn is not None:
            with self._conn:
                self._conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS seen (
                        dedup_key TEXT PRIMARY KEY
                    )
                    """
                )
                self._conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS tasks (
                        task_id TEXT PRIMARY KEY,
                        url TEXT NOT NULL,
                        priority INT NOT NULL,
                        payload_json TEXT NOT NULL,
                        attempts INT NOT NULL,
                        max_attempts INT NOT NULL,
                        dedup_key TEXT NOT NULL,
                        created_at REAL NOT NULL,
                        last_error TEXT,
                        status TEXT NOT NULL
                    )
                    """
                )

    async def push(self, task: ScrapingTask) -> bool:
        """Сохраняет задачу в базы данных SQLite.

        Args:
            task: Задача для сохранения.

        Returns:
            True, если задача сохранена; False, если задача дедуплицирована.
        """
        async with self._lock:
            if self._conn is None:
                return False
            try:
                self._conn.execute("INSERT INTO seen (dedup_key) VALUES (?)", (task.dedup_key,))
            except sqlite3.IntegrityError:
                return False

            self._conn.execute(
                """
                INSERT INTO tasks (
                    task_id, url, priority, payload_json, attempts,
                    max_attempts, dedup_key, created_at, last_error, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')
                """,
                (
                    task.task_id,
                    task.url,
                    task.priority,
                    json.dumps(task.payload),
                    task.attempts,
                    task.max_attempts,
                    task.dedup_key,
                    task.created_at,
                    task.last_error,
                ),
            )
            self._conn.commit()
            return True

    async def pop(self) -> ScrapingTask | None:
        """Извлекает следующую ожидающую задачу из базы данных SQLite.

        Returns:
            Экземпляр ScrapingTask или None, если очередь пуста.
        """
        async with self._lock:
            if self._conn is None:
                return None
            row = self._conn.execute(
                """
                SELECT * FROM tasks
                WHERE status = 'pending'
                ORDER BY priority DESC, created_at ASC
                LIMIT 1
                """
            ).fetchone()

            if row is None:
                return None

            self._conn.execute("UPDATE tasks SET status = 'processing' WHERE task_id = ?", (row["task_id"],))
            self._conn.commit()

            return ScrapingTask(
                url=row["url"],
                priority=row["priority"],
                payload=json.loads(row["payload_json"]),
                attempts=row["attempts"],
                max_attempts=row["max_attempts"],
                task_id=row["task_id"],
                dedup_key=row["dedup_key"],
                created_at=row["created_at"],
                last_error=row["last_error"],
            )

    async def complete(self, task: ScrapingTask) -> None:
        """Обновляет статус задачи в БД на 'completed'.

        Args:
            task: Выполненная задача.
        """
        async with self._lock:
            if self._conn is not None:
                self._conn.execute("UPDATE tasks SET status = 'completed' WHERE task_id = ?", (task.task_id,))
                self._conn.commit()

    async def fail(self, task: ScrapingTask, error: str) -> None:
        """Обновляет количество попыток и статус сбойной задачи в БД.

        Args:
            task: Сбойная задача.
            error: Текст ошибки.
        """
        async with self._lock:
            if self._conn is not None:
                task.last_error = error
                task.attempts += 1
                new_status = "pending" if task.attempts < task.max_attempts else "failed"

                self._conn.execute(
                    """
                    UPDATE tasks
                    SET attempts = ?, last_error = ?, status = ?
                    WHERE task_id = ?
                    """,
                    (task.attempts, task.last_error, new_status, task.task_id),
                )
                self._conn.commit()

    async def size(self) -> int:
        """Подсчитывает количество ожидающих задач в БД.

        Returns:
            Количество задач со статусом 'pending'.
        """
        async with self._lock:
            if self._conn is None:
                return 0
            row = self._conn.execute("SELECT COUNT(*) FROM tasks WHERE status = 'pending'").fetchone()
            return int(row[0]) if row else 0

    async def clear(self) -> None:
        """Удаляет все записи очередей и истории дедупликации из БД."""
        async with self._lock:
            if self._conn is not None:
                self._conn.execute("DELETE FROM seen")
                self._conn.execute("DELETE FROM tasks")
                self._conn.commit()

    async def close(self) -> None:
        """Освобождает ресурсы и закрывает подключение к SQLite."""
        async with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None


class RedisTaskQueue(BaseTaskQueue):
    """Распределенная очередь задач на базе Redis."""

    def __init__(self, redis_url: str = "redis://localhost:6379/0", queue_name: str = "scraping_queue") -> None:
        try:
            import redis.asyncio as redis_async
        except ImportError:
            raise OptionalDependencyError(
                "Библиотека redis не установлена.",
                dependency="redis",
                hint="Установите её с помощью 'pip install chutils[redis]'.",
            )
        self.redis_url = redis_url
        self.queue_name = queue_name
        self._client = redis_async.from_url(redis_url)

    async def push(self, task: ScrapingTask) -> bool:
        """Добавляет задачу в структуру Redis ZSET.

        Args:
            task: Задача для добавления.

        Returns:
            True, если задача добавлена; False, если задача дедуплицирована.
        """
        seen_key = f"{self.queue_name}:seen"
        zset_key = f"{self.queue_name}:pending"
        data_key = f"{self.queue_name}:task:{task.task_id}"

        added = await self._client.sadd(seen_key, task.dedup_key)
        if not added:
            return False

        task_data = {
            "task_id": task.task_id,
            "url": task.url,
            "priority": task.priority,
            "payload": task.payload,
            "attempts": task.attempts,
            "max_attempts": task.max_attempts,
            "dedup_key": task.dedup_key,
            "created_at": task.created_at,
            "last_error": task.last_error,
        }
        await self._client.set(data_key, json.dumps(task_data))
        await self._client.zadd(zset_key, {task.task_id: -task.priority})
        return True

    async def pop(self) -> ScrapingTask | None:
        """Извлекает наивысшую по приоритету задачу из Redis.

        Returns:
            Экземпляр ScrapingTask или None, если очередь пуста.
        """
        zset_key = f"{self.queue_name}:pending"
        res = await self._client.zpopmin(zset_key)
        if not res:
            return None

        task_id = res[0][0].decode("utf-8") if isinstance(res[0][0], bytes) else res[0][0]
        data_key = f"{self.queue_name}:task:{task_id}"
        raw_data = await self._client.get(data_key)
        if not raw_data:
            return None

        data = json.loads(raw_data)
        return ScrapingTask(**data)

    async def complete(self, task: ScrapingTask) -> None:
        """Удаляет данные выполненной задачи из Redis.

        Args:
            task: Выполненная задача.
        """
        data_key = f"{self.queue_name}:task:{task.task_id}"
        await self._client.delete(data_key)

    async def fail(self, task: ScrapingTask, error: str) -> None:
        """Обрабатывает ошибку задачи и помещает ее обратно при наличии попыток.

        Args:
            task: Сбойная задача.
            error: Сообщение об ошибке.
        """
        task.last_error = error
        task.attempts += 1

        if task.attempts < task.max_attempts:
            zset_key = f"{self.queue_name}:pending"
            data_key = f"{self.queue_name}:task:{task.task_id}"
            task_data = {
                "task_id": task.task_id,
                "url": task.url,
                "priority": task.priority,
                "payload": task.payload,
                "attempts": task.attempts,
                "max_attempts": task.max_attempts,
                "dedup_key": task.dedup_key,
                "created_at": task.created_at,
                "last_error": task.last_error,
            }
            await self._client.set(data_key, json.dumps(task_data))
            await self._client.zadd(zset_key, {task.task_id: -task.priority})

    async def size(self) -> int:
        """Возвращает количество элементов в очереди Redis.

        Returns:
            Число элементов.
        """
        zset_key = f"{self.queue_name}:pending"
        return int(await self._client.zcard(zset_key))

    async def clear(self) -> None:
        """Удаляет ключи очереди из Redis."""
        seen_key = f"{self.queue_name}:seen"
        zset_key = f"{self.queue_name}:pending"
        await self._client.delete(seen_key, zset_key)
