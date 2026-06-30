"""
Реализация легковесного планировщика фоновых задач.
"""
from __future__ import annotations

import functools
import inspect
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Any, Optional, List


class ErrorStrategy(str, Enum):
    """Стратегии обработки ошибок в периодических задачах."""
    IGNORE = "IGNORE"
    STOP_TASK = "STOP_TASK"
    STOP_SCHEDULER = "STOP_SCHEDULER"


@dataclass
class PeriodicTask:
    """Метаданные периодической задачи."""
    func: Callable[..., Any]
    interval_seconds: int
    run_immediately: bool = False
    overlap: bool = False
    error_strategy: ErrorStrategy = ErrorStrategy.IGNORE
    name: Optional[str] = None

    def __post_init__(self) -> None:
        if self.name is None:
            self.name = self.func.__name__
        self.is_async = inspect.iscoroutinefunction(self.func)


# Глобальный реестр зарегистрированных задач
_tasks_registry: List[PeriodicTask] = []


def periodic_task(
        interval_seconds: int,
        run_immediately: bool = False,
        overlap: bool = False,
        error_strategy: ErrorStrategy = ErrorStrategy.IGNORE,
        name: Optional[str] = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Декоратор для привязки функции к расписанию планировщика задач.

    Args:
        interval_seconds: Интервал запуска в секундах.
        run_immediately: Если True, задача запустится сразу при старте планировщика.
        overlap: Если True, задача запускается независимо от предыдущих запусков.
        error_strategy: Стратегия обработки ошибок.
        name: Пользовательское имя задачи.
    """
    if interval_seconds <= 0:
        raise ValueError("Interval must be a positive integer")

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        task = PeriodicTask(
            func=func,
            interval_seconds=interval_seconds,
            run_immediately=run_immediately,
            overlap=overlap,
            error_strategy=error_strategy,
            name=name
        )
        _tasks_registry.append(task)

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return func(*args, **kwargs)

        return wrapper

    return decorator


def get_registered_tasks() -> List[PeriodicTask]:
    """Возвращает список зарегистрированных задач."""
    return _tasks_registry


def clear_tasks_registry() -> None:
    """Очищает реестр зарегистрированных задач (для тестов)."""
    _tasks_registry.clear()
