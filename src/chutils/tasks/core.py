"""
Реализация легковесного планировщика фоновых задач.
"""
from __future__ import annotations

import asyncio
import functools
import inspect
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Any, Optional, List, Dict

from chutils.lifecycle import register_cleanup

logger = logging.getLogger("chutils.tasks")


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
    name: str = ""

    def __post_init__(self) -> None:
        if not self.name:
            self.name = self.func.__name__
        self.is_async = inspect.iscoroutinefunction(self.func)


# Глобальный реестр зарегистрированных задач
_tasks_registry: List[PeriodicTask] = []


def periodic_task(
        interval_seconds: int,
        run_immediately: bool = False,
        overlap: bool = False,
        error_strategy: ErrorStrategy = ErrorStrategy.IGNORE,
        name: str = "",
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


class StopTaskException(Exception):
    """Исключение для остановки отдельной задачи."""
    pass


class StopSchedulerException(Exception):
    """Исключение для остановки всего планировщика."""
    pass


class TaskScheduler:
    """Асинхронный планировщик фоновых задач."""

    def __init__(self) -> None:
        self._running_tasks: Dict[str, asyncio.Task[Any]] = {}
        self._locks: Dict[str, asyncio.Lock] = {}
        self._shutdown_event = asyncio.Event()
        self._tasks: List[PeriodicTask] = []

    async def _run_task(self, task: PeriodicTask) -> None:
        """Внутренний цикл выполнения отдельной периодической задачи."""
        if not task.run_immediately:
            try:
                await asyncio.sleep(task.interval_seconds)
            except asyncio.CancelledError:
                return

        while not self._shutdown_event.is_set():
            # Проверка перекрытия (overlapping)
            if not task.overlap:
                if self._locks[task.name].locked():
                    logger.warning(
                        "Запуск задачи '%s' пропущен, так как предыдущее выполнение еще не завершено.",
                        task.name
                    )
                    try:
                        await asyncio.sleep(task.interval_seconds)
                    except asyncio.CancelledError:
                        break
                    continue

            # Локальная обертка для выполнения
            async def execute_and_handle_errors() -> None:
                try:
                    if task.is_async:
                        await task.func()
                    else:
                        await asyncio.to_thread(task.func)
                except Exception as e:
                    logger.exception("Ошибка при выполнении задачи '%s': %s", task.name, e)

                    if task.error_strategy == ErrorStrategy.STOP_TASK:
                        logger.error("Задача '%s' исключена из планировщика из-за ошибки.", task.name)
                        raise StopTaskException()
                    elif task.error_strategy == ErrorStrategy.STOP_SCHEDULER:
                        logger.critical("Критическая ошибка в задаче '%s'. Инициируется остановка планировщика.",
                                        task.name)
                        raise StopSchedulerException()

            try:
                if task.overlap:
                    # Запускаем в фоновом режиме, не блокируя цикл планировщика
                    asyncio.create_task(execute_and_handle_errors())
                else:
                    async with self._locks[task.name]:
                        await execute_and_handle_errors()
            except StopTaskException:
                break
            except StopSchedulerException:
                # Асинхронно останавливаем планировщик
                asyncio.create_task(stop_scheduler())
                break
            except asyncio.CancelledError:
                break
            except Exception:
                pass

            try:
                await asyncio.sleep(task.interval_seconds)
            except asyncio.CancelledError:
                break

    async def start(self) -> None:
        """Запускает все зарегистрированные периодические задачи."""
        self._shutdown_event.clear()
        self._tasks = get_registered_tasks()

        for task in self._tasks:
            if task.name not in self._locks:
                self._locks[task.name] = asyncio.Lock()

            job = asyncio.create_task(self._run_task(task), name=f"scheduler_job_{task.name}")
            self._running_tasks[task.name] = job

        logger.info("Планировщик фоновых задач запущен. Задач в работе: %d", len(self._tasks))

    async def stop(self) -> None:
        """Останавливает планировщик и все запущенные задачи."""
        if self._shutdown_event.is_set():
            logger.debug("Планировщик уже останавливается или остановлен.")
            return

        logger.info("Остановка планировщика фоновых задач...")
        self._shutdown_event.set()

        for name, job in list(self._running_tasks.items()):
            if not job.done():
                logger.debug("Отмена задачи: %s", name)
                job.cancel()

        if self._running_tasks:
            logger.debug("Ожидание завершения %d задач...", len(self._running_tasks))
            await asyncio.gather(*self._running_tasks.values(), return_exceptions=True)

        self._running_tasks.clear()
        logger.info("Планировщик фоновых задач остановлен.")


# Глобальный синглтон планировщика
_scheduler: Optional[TaskScheduler] = None


def start_scheduler() -> None:
    """
    Запускает глобальный планировщик фоновых задач в текущем Event Loop.
    """
    global _scheduler
    if _scheduler is not None:
        logger.warning("Планировщик фоновых задач уже запущен.")
        return

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        logger.error("Не удалось запустить планировщик: отсутствует активный Event Loop.")
        raise RuntimeError("No running event loop")

    _scheduler = TaskScheduler()

    # Регистрируем хук в lifecycle для Graceful Shutdown
    register_cleanup(stop_scheduler)

    # Запускаем в фоновом режиме
    loop.create_task(_scheduler.start())


async def stop_scheduler() -> None:
    """
    Останавливает глобальный планировщик фоновых задач.
    """
    global _scheduler
    if _scheduler is None:
        logger.debug("stop_scheduler() вызван, но планировщик не запущен (уже None).")
        return

    logger.debug("Вызов stop_scheduler()...")
    await _scheduler.stop()
    _scheduler = None
    logger.debug("stop_scheduler() завершен, _scheduler сброшен в None.")
