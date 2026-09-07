"""
Модуль chutils.scraping.concurrency: Умная очередь задач, распределение нагрузки и воркеры.
"""

from .base import BaseTaskQueue
from .limiter import DomainRateLimiter
from .models import ScrapingTask
from .pool import WorkerPool
from .queues import InMemoryTaskQueue, PersistentTaskQueue, RedisTaskQueue

__all__ = [
    "BaseTaskQueue",
    "DomainRateLimiter",
    "InMemoryTaskQueue",
    "PersistentTaskQueue",
    "RedisTaskQueue",
    "ScrapingTask",
    "WorkerPool",
]
