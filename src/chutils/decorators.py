import functools
import logging
import time
from typing import Optional

# Ленивая инициализация логгера
_module_logger: Optional[logging.Logger] = None


def _get_logger() -> logging.Logger:
    """Получает лениво инициализированный логгер модуля."""
    global _module_logger
    if _module_logger is None:
        from . import logger as chutils_logger
        _module_logger = chutils_logger.setup_logger(__name__)
    return _module_logger


def log_function_details(func):
    """
    Декоратор для логирования деталей вызова функции: аргументы,
    время выполнения и возвращаемое значение.

    Логирование происходит на уровне DEVDEBUG.

    Example:
        ```python
        from chutils import log_function_details, setup_logger

        # Чтобы видеть вывод, нужно установить уровень логгера на DEVDEBUG
        # в коде или в файле config.yml
        setup_logger(log_level_str="DEVDEBUG")

        @log_function_details
        def add(a, b):
            return a + b

        add(2, 3)

        # В логах появится информация о вызове, времени выполнения и результате.
        ```
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        _get_logger().devdebug("Вызов функции: %s() с аргументами %s и %s", func.__name__, args, kwargs)
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        end_time = time.perf_counter()
        run_time = end_time - start_time
        _get_logger().devdebug("Функция %s() завершилась за %.4f с. Возвращаемое значение: %s",
                             func.__name__, run_time, result)
        return result

    return wrapper
