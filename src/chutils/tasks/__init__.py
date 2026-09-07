"""
Модуль планировщика фоновых задач.
"""

from chutils.tasks.core import (
    ErrorStrategy,
    PeriodicTask,
    clear_tasks_registry,
    get_registered_tasks,
    periodic_task,
    start_scheduler,
    stop_scheduler,
)

__all__ = [
    "ErrorStrategy",
    "PeriodicTask",
    "clear_tasks_registry",
    "get_registered_tasks",
    "periodic_task",
    "start_scheduler",
    "stop_scheduler",
]
