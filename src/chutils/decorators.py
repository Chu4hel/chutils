"""
Модуль с полезными декораторами для автоматизации задач.

Включает инструменты для логирования производительности и деталей вызовов функций.
"""

import functools
import time
from typing import Optional, TYPE_CHECKING

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
