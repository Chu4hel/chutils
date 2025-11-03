import functools
import time
from . import logger

# Настраиваем логгер для этого модуля
log = logger.setup_logger(__name__)


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
        log.devdebug(f"Вызов функции: {func.__name__}() с аргументами {args} и {kwargs}")
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        end_time = time.perf_counter()
        run_time = end_time - start_time
        log.devdebug(f"Функция {func.__name__}() завершилась за {run_time:.4f} с. "
                     f"Возвращаемое значение: {result}")
        return result

    return wrapper
