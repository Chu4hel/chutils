"""Ядро шины событий (In-Memory Event Bus)."""

import asyncio
import inspect
import logging
import threading
import typing as t
from collections import defaultdict
from collections.abc import Callable
from enum import Enum

from chutils.exceptions import EventBusExceptionGroup

logger = logging.getLogger(__name__)

# Безопасный импорт Pydantic
try:
    import pydantic
    BaseModel = pydantic.BaseModel
except ImportError:
    BaseModel = None  # type: ignore[assignment,misc]

# Фоновый event loop для асинхронных задач, запускаемых из синхронного контекста
_background_loop: asyncio.AbstractEventLoop | None = None
_background_thread: threading.Thread | None = None
_loop_lock = threading.Lock()

def _start_background_loop() -> asyncio.AbstractEventLoop:
    """Лениво запускает фоновый event loop в отдельном демоническом потоке."""
    global _background_loop, _background_thread
    with _loop_lock:
        if _background_loop is None:
            loop = asyncio.new_event_loop()
            thread = threading.Thread(
                target=loop.run_forever,
                name="ChutilsEventBusLoop",
                daemon=True
            )
            thread.start()
            _background_loop = loop
            _background_thread = thread
        return _background_loop

def is_async_callable(obj: t.Any) -> bool:
    """Проверяет, является ли вызываемый объект асинхронным."""
    if inspect.iscoroutinefunction(obj):
        return True
    if hasattr(obj, "__call__"):
        return inspect.iscoroutinefunction(obj.__call__)
    return False

def _is_pydantic_model_instance(obj: t.Any) -> bool:
    """Проверяет, является ли объект экземпляром Pydantic-модели."""
    if BaseModel is None:
        return False
    return isinstance(obj, BaseModel)

async def _run_and_log_errors(coro: t.Coroutine[t.Any, t.Any, t.Any], event_name: str) -> None:
    """Обертка для безопасного выполнения корутины и логирования ошибок."""
    try:
        await coro
    except Exception as e:
        logger.error("Ошибка в асинхронном фоновом обработчике события %s: %s", event_name, e, exc_info=True)


class ErrorStrategy(str, Enum):
    """Стратегия обработки ошибок при выполнении обработчиков событий."""
    IGNORE = "ignore"
    FAIL_FAST = "fail_fast"
    COLLECT = "collect"


class EventBus:
    """Внутренняя шина событий (In-Memory Event Bus).

    Обеспечивает регистрацию подписчиков и публикацию событий.
    Потокобезопасна.
    """

    def __init__(self, error_strategy: ErrorStrategy = ErrorStrategy.IGNORE) -> None:
        """Инициализирует шину событий.

        Args:
            error_strategy: Стратегия обработки ошибок по умолчанию.
        """
        self._subscribers: dict[str, list[Callable[..., t.Any]]] = defaultdict(list)
        self._lock = threading.Lock()
        self.error_strategy = error_strategy

    def subscribe(self, event_name: str) -> Callable[[Callable[..., t.Any]], Callable[..., t.Any]]:
        """Декоратор для регистрации обработчика события на данном инстансе шины.

        Args:
            event_name: Имя события, на которое подписывается обработчик.

        Returns:
            Декоратор, который регистрирует функцию-обработчик и возвращает её.
        """
        def decorator(func: Callable[..., t.Any]) -> Callable[..., t.Any]:
            with self._lock:
                if func not in self._subscribers[event_name]:
                    self._subscribers[event_name].append(func)
            return func
        return decorator

    def unsubscribe(self, event_name: str, func: Callable[..., t.Any]) -> None:
        """Отменяет подписку обработчика на событие.

        Args:
            event_name: Имя события.
            func: Функция-обработчик, которую нужно отписать.
        """
        with self._lock:
            if event_name in self._subscribers:
                try:
                    self._subscribers[event_name].remove(func)
                except ValueError:
                    pass

    def _resolve_payload(self, args: tuple[t.Any, ...], kwargs: dict[str, t.Any]) -> tuple[tuple[t.Any, ...], dict[str, t.Any]]:
        """Определяет формат переданных аргументов.

        Если передан единственный аргумент, и это экземпляр Pydantic-модели,
        он возвращается как единственный позиционный аргумент.
        """
        if len(args) == 1 and not kwargs and _is_pydantic_model_instance(args[0]):
            return args, kwargs
        return args, kwargs

    def publish(self, event_name: str, *args: t.Any, error_strategy: ErrorStrategy | None = None, **kwargs: t.Any) -> None:
        """Синхронно публикует событие.

        Синхронные обработчики выполняются немедленно в текущем потоке.
        Асинхронные обработчики запускаются в фоновом режиме в выделенном Event Loop.

        Args:
            event_name: Имя события.
            *args: Позиционные аргументы для обработчиков.
            error_strategy: Стратегия обработки ошибок для этого вызова.
            **kwargs: Именованные аргументы для обработчиков.
        """
        args, kwargs = self._resolve_payload(args, kwargs)
        strategy = error_strategy or self.error_strategy

        with self._lock:
            subscribers = list(self._subscribers.get(event_name, []))

        if not subscribers:
            return

        sync_errors: list[Exception] = []

        for func in subscribers:
            if is_async_callable(func):
                loop = _start_background_loop()
                coro = func(*args, **kwargs)
                asyncio.run_coroutine_threadsafe(_run_and_log_errors(coro, event_name), loop)
            else:
                try:
                    func(*args, **kwargs)
                except Exception as e:
                    if strategy == ErrorStrategy.FAIL_FAST:
                        raise e
                    elif strategy == ErrorStrategy.COLLECT:
                        sync_errors.append(e)
                    else:  # IGNORE
                        logger.error("Ошибка в синхронном обработчике события %s: %s", event_name, e, exc_info=True)

        if strategy == ErrorStrategy.COLLECT and sync_errors:
            raise EventBusExceptionGroup(
                f"При синхронной публикации события '{event_name}' произошли ошибки.",
                sync_errors
            )

    async def publish_async(self, event_name: str, *args: t.Any, error_strategy: ErrorStrategy | None = None, **kwargs: t.Any) -> None:
        """Асинхронно публикует событие.

        Дожидается выполнения всех подписчиков (как синхронных, так и асинхронных).
        Синхронные обработчики выполняются в пуле потоков через asyncio.to_thread.

        Args:
            event_name: Имя события.
            *args: Позиционные аргументы для обработчиков.
            error_strategy: Стратегия обработки ошибок для этого вызова.
            **kwargs: Именованные аргументы для обработчиков.
        """
        args, kwargs = self._resolve_payload(args, kwargs)
        strategy = error_strategy or self.error_strategy

        with self._lock:
            subscribers = list(self._subscribers.get(event_name, []))

        if not subscribers:
            return

        tasks = []
        for func in subscribers:
            if is_async_callable(func):
                tasks.append(func(*args, **kwargs))
            else:
                tasks.append(asyncio.to_thread(func, *args, **kwargs))

        if strategy == ErrorStrategy.FAIL_FAST:
            # При FAIL_FAST любое исключение немедленно прерывает gather
            await asyncio.gather(*tasks, return_exceptions=False)
        else:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            errors = [res for res in results if isinstance(res, Exception)]

            if errors:
                if strategy == ErrorStrategy.COLLECT:
                    raise EventBusExceptionGroup(
                        f"При асинхронной публикации события '{event_name}' произошли ошибки.",
                        errors
                    )
                else:  # IGNORE
                    for err in errors:
                        logger.error("Ошибка в обработчике события %s: %s", event_name, err, exc_info=True)


# Глобальный инстанс шины событий
_global_bus = EventBus()

def subscribe(event_name: str) -> Callable[[Callable[..., t.Any]], Callable[..., t.Any]]:
    """Декоратор для подписки на событие в глобальной шине.

    Args:
        event_name: Имя события.

    Returns:
        Декоратор для функции-обработчика.
    """
    return _global_bus.subscribe(event_name)

def publish(event_name: str, *args: t.Any, error_strategy: ErrorStrategy | None = None, **kwargs: t.Any) -> None:
    """Синхронно публикует событие в глобальной шине.

    Args:
        event_name: Имя события.
        *args: Позиционные аргументы.
        error_strategy: Стратегия обработки ошибок.
        **kwargs: Именованные аргументы.
    """
    _global_bus.publish(event_name, *args, error_strategy=error_strategy, **kwargs)

async def publish_async(event_name: str, *args: t.Any, error_strategy: ErrorStrategy | None = None, **kwargs: t.Any) -> None:
    """Асинхронно публикует событие в глобальной шине.

    Args:
        event_name: Имя события.
        *args: Позиционные аргументы.
        error_strategy: Стратегия обработки ошибок.
        **kwargs: Именованные аргументы.
    """
    await _global_bus.publish_async(event_name, *args, error_strategy=error_strategy, **kwargs)
