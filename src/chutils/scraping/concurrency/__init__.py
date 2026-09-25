"""
Модуль chutils.scraping.concurrency: Умная очередь задач, распределение нагрузки и воркеры.
"""

from .base import BaseTaskQueue
from .limiter import DomainRateLimiter
from .models import ScrapingTask
from .pool import WorkerPool
from .queues import InMemoryTaskQueue, PersistentTaskQueue, RedisTaskQueue
from .reaper import (
    IdleBrowserReaper,
    IdleBrowserReaperConfig,
    IdleReaper,
    IdleReaperConfig,
)

__all__ = [
    "BaseTaskQueue",
    "DomainRateLimiter",
    "IdleBrowserReaper",
    "IdleBrowserReaperConfig",
    "IdleReaper",
    "IdleReaperConfig",
    "InMemoryTaskQueue",
    "PersistentTaskQueue",
    "RedisTaskQueue",
    "ScrapingTask",
    "WorkerPool",
]

