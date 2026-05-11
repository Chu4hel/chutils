"""
Модуль с полезными декораторами для автоматизации задач.

Включает инструменты для логирования производительности и деталей вызовов функций.
"""

import asyncio
import functools
import inspect
import random
import time
from typing import Optional, TYPE_CHECKING, Tuple, Type, Any, Callable

if TYPE_CHECKING:
    from .logger import ChutilsLogger

# Ленивая инициализация логгера
_module_logger: Optional['ChutilsLogger'] = None


def _get_logger() -> 'ChutilsLogger':
    """
    Получает лениво инициализированный логгер модуля.

    Returns:
        Экземпляр ChutilsLogger.
    """
    global _module_logger
    if _module_logger is None:
        from . import logger as chutils_logger
        _module_logger = chutils_logger.setup_logger(__name__)
    return _module_logger  # type: ignore


def retry(
        retries: int = 3,
        delay: float = 1.0,
        backoff: float = 2.0,
        jitter: bool = False,
        exceptions: Tuple[Type[Exception], ...] = (Exception,),
) -> Callable:
    """
    Декоратор для автоматического повторного выполнения функции при возникновении исключений.

    Args:
        retries: Количество попыток повтора (не считая первый запуск).
        delay: Базовая задержка между попытками в секундах.
        backoff: Множитель задержки для каждой следующей попытки.
        jitter: Добавлять ли случайный шум к задержке.
        exceptions: Кортеж исключений, при которых требуется повтор.

    Returns:
        Декоратор функции.
    """

    def decorator(func: Callable) -> Callable:
        if inspect.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                current_delay = delay
                for i in range(retries + 1):
                    try:
                        return await func(*args, **kwargs)
                    except exceptions as e:
                        if i == retries:
                            raise

                        _get_logger().warning(
                            "Попытка %d/%d завершилась ошибкой: %s. Повтор через %.2f с...",
                            i + 1, retries, e, current_delay
                        )

                        sleep_time = current_delay
                        if jitter:
                            sleep_time += random.uniform(0, 0.1 * current_delay)

                        await asyncio.sleep(sleep_time)
                        current_delay *= backoff

            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                current_delay = delay
                for i in range(retries + 1):
                    try:
                        return func(*args, **kwargs)
                    except exceptions as e:
                        if i == retries:
                            raise

                        _get_logger().warning(
                            "Попытка %d/%d завершилась ошибкой: %s. Повтор через %.2f с...",
                            i + 1, retries, e, current_delay
                        )

                        sleep_time = current_delay
                        if jitter:
                            sleep_time += random.uniform(0, 0.1 * current_delay)

                        time.sleep(sleep_time)
                        current_delay *= backoff

            return sync_wrapper

    return decorator


def log_function_details(func):
    """
    Декоратор для логирования деталей вызова функции.

    Записывает аргументы, время выполнения и возвращаемое значение на уровне DEVDEBUG.

    Args:
        func: Декорируемая функция.

    Returns:
        Обертка функции с логированием.

    Example:
        ```python
        @log_function_details
        def add(a, b):
            return a + b

        add(2, 3)
        ```
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        _get_logger().devdebug("Вызов функции: %s() с аргументами %s и %s", func.__name__, args, kwargs)
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        end_time = time.perf_counter()
        run_time = end_time - start_time
        _get_logger().devdebug("Функция %s() завершилась за %.4f с. Результат: %s",
                               func.__name__, run_time, result)
        return result

    return wrapper
