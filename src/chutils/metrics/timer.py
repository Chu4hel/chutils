import asyncio
import functools
import time
from typing import Any, Callable, Dict, Optional, TypeVar

F = TypeVar("F", bound=Callable[..., Any])


def _observe_lazy(name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
    # Ленивый импорт во избежание циклической зависимости при инициализации пакета
    from . import observe
    observe(name, value, labels)


class TimerContext:
    """
    Контекстный менеджер и декоратор для замера времени выполнения функций и блоков кода.
    
    Пример использования в качестве контекстного менеджера:
        with timer("db_query_duration_seconds", labels={"op": "select"}):
            db.execute("SELECT ...")
            
    Пример использования в качестве декоратора:
        @timer("http_request_duration_seconds", labels={"endpoint": "/users"})
        def handle():
            ...
    """

    def __init__(self, name: str, labels: Optional[Dict[str, str]] = None) -> None:
        self.name = name
        self.labels = labels
        self.start_time: Optional[float] = None

    def __enter__(self) -> "TimerContext":
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self.start_time is not None:
            duration = time.perf_counter() - self.start_time
            _observe_lazy(self.name, duration, self.labels)

    def __call__(self, func: F) -> F:
        is_async = asyncio.iscoroutinefunction(func)

        if is_async:
            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                start = time.perf_counter()
                try:
                    return await func(*args, **kwargs)
                finally:
                    duration = time.perf_counter() - start
                    _observe_lazy(self.name, duration, self.labels)
            return async_wrapper  # type: ignore[return-value]
        else:
            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                start = time.perf_counter()
                try:
                    return func(*args, **kwargs)
                finally:
                    duration = time.perf_counter() - start
                    _observe_lazy(self.name, duration, self.labels)
            return sync_wrapper  # type: ignore[return-value]


def timer(name: str, labels: Optional[Dict[str, str]] = None) -> TimerContext:
    """
    Фабричная функция для создания объекта TimerContext.
    """
    return TimerContext(name, labels)
