"""
Пул асинхронных и синхронных воркеров для параллельной обработки задач скрапинга.
"""

from __future__ import annotations

import asyncio
import inspect
import time
from typing import Any, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from .base import BaseTaskQueue
    from .limiter import DomainRateLimiter
    from .models import ScrapingTask


class WorkerPool:
    """Управляющий пул воркеров с поддержкой асинхронных и синхронных обработчиков."""

    def __init__(
        self,
        queue: BaseTaskQueue,
        handler: Callable[[ScrapingTask], Any],
        limiter: DomainRateLimiter | None = None,
        max_workers: int = 5,
        retry_backoff: float = 2.0,
    ) -> None:
        """Инициализирует пул воркеров.

        Args:
            queue: Очередь задач скрапинга.
            handler: Синхронная или асинхронная функция-обработчик задач.
            limiter: Опциональный DomainRateLimiter для контроля нагрузки.
            max_workers: Количество параллельных воркеров.
            retry_backoff: Коэффициент повторного вызова (backoff).
        """
        self.queue = queue
        self.handler = handler
        self.limiter = limiter
        self.max_workers = max_workers
        self.retry_backoff = retry_backoff

        self._running = False
        self._workers: list[asyncio.Task[None]] = []
        self._active_workers_count = 0
        self._lock = asyncio.Lock()
        self._completed_count = 0
        self._failed_count = 0

    @property
    def completed_count(self) -> int:
        """Количество успешно выполненных задач."""
        return self._completed_count

    @property
    def failed_count(self) -> int:
        """Количество проваленных задач."""
        return self._failed_count

    async def _execute_handler(self, task: ScrapingTask) -> None:
        if inspect.iscoroutinefunction(self.handler):
            await self.handler(task)
        else:
            await asyncio.to_thread(self.handler, task)

    async def _worker_loop(self) -> None:
        while self._running:
            task = await self.queue.pop()
            if task is None:
                await asyncio.sleep(0.05)
                continue

            async with self._lock:
                self._active_workers_count += 1
                metrics_collector = getattr(self.queue, "metrics", None)
                if metrics_collector:
                    metrics_collector.set_active_workers(self._active_workers_count)

            start_time = time.monotonic()
            status = "completed"
            try:
                if self.limiter:
                    await self.limiter.acquire(task.url)

                await self._execute_handler(task)
                await self.queue.complete(task)
                self._completed_count += 1
            except Exception as e:
                status = "failed"
                await self.queue.fail(task, str(e))
                self._failed_count += 1
            finally:
                duration = time.monotonic() - start_time
                metrics_collector = getattr(self.queue, "metrics", None)
                if metrics_collector:
                    metrics_collector.observe_execution_duration(duration, status=status)
                    metrics_collector.inc_tasks_processed(status=status)

                if self.limiter:
                    self.limiter.release(task.url)
                async with self._lock:
                    self._active_workers_count -= 1
                    if metrics_collector:
                        metrics_collector.set_active_workers(self._active_workers_count)

    async def start(self) -> None:
        """Запускает фоновые задачи воркеров."""
        if self._running:
            return
        self._running = True
        self._workers = [
            asyncio.create_task(self._worker_loop())
            for _ in range(self.max_workers)
        ]

    async def stop(self) -> None:
        """Останавливает все воркеры."""
        self._running = False
        for worker in self._workers:
            worker.cancel()
        if self._workers:
            await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()

    async def run_until_complete(self, poll_interval: float = 0.05) -> None:
        """Запускает пул и выполняет задачи до полного опустошения очереди.

        Args:
            poll_interval: Интервал проверки состояния очереди в секундах.
        """
        await self.start()
        try:
            while True:
                size = await self.queue.size()
                async with self._lock:
                    active = self._active_workers_count

                if size == 0 and active == 0:
                    break
                await asyncio.sleep(poll_interval)
        finally:
            await self.stop()
