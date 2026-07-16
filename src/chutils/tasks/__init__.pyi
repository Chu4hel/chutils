from collections.abc import Awaitable
from enum import Enum
from typing import Any, Callable


class ErrorStrategy(str, Enum):
    IGNORE = "IGNORE"
    STOP_TASK = "STOP_TASK"
    STOP_SCHEDULER = "STOP_SCHEDULER"


class PeriodicTask:
    func: Callable[[], Any] | Callable[[], Awaitable[Any]]
    interval_seconds: int | Callable[[], int] | str
    run_immediately: bool
    overlap: bool
    error_strategy: ErrorStrategy
    name: str

    def __init__(
            self,
            func: Callable[[], Any] | Callable[[], Awaitable[Any]],
            interval_seconds: int | Callable[[], int] | str,
            run_immediately: bool = False,
            overlap: bool = False,
            error_strategy: ErrorStrategy = ErrorStrategy.IGNORE,
            name: str = "",
    ) -> None: ...


def periodic_task(
        interval_seconds: int | Callable[[], int] | str,
        run_immediately: bool = False,
        overlap: bool = False,
        error_strategy: ErrorStrategy = ErrorStrategy.IGNORE,
        name: str = "",
) -> Callable[[Callable[..., Any]], Callable[..., Any]]: ...


def get_registered_tasks() -> list[PeriodicTask]: ...


def clear_tasks_registry() -> None: ...


def start_scheduler() -> None: ...


async def stop_scheduler() -> None: ...
