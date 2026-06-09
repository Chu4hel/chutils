"""
Модуль с полезными декораторами для автоматизации задач.

Включает инструменты для логирования производительности и деталей вызовов функций.
"""
import asyncio
import concurrent.futures
import functools
import inspect
import random
import time
from typing import Optional, TYPE_CHECKING, Tuple, Type, Any, Callable, Union

from .exceptions import ChutilsTimeoutError
from .typing import P, R

if TYPE_CHECKING:
    from .logger import ChutilsLogger

# Уникальный маркер для определения, был ли передан fallback (позволяет передавать None)
_NO_FALLBACK = object()

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

    # Используем cast или проверку, чтобы избежать Any
    if _module_logger is None:
        raise RuntimeError("Не удалось инициализировать логгер модуля decorators")
    return _module_logger


def retry(
        retries: int = 3,
        delay: float = 1.0,
        backoff: float = 2.0,
        jitter: bool = False,
        exceptions: Tuple[Type[Exception], ...] = (Exception,),
) -> Callable[[Callable[P, R]], Callable[P, R]]:
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

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        if inspect.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                current_delay = delay
                for i in range(retries + 1):
                    try:
                        return await func(*args, **kwargs)  # type: ignore[no-any-return]
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
                # MyPy может ругаться, что не все пути возвращают значение,
                # но raise в цикле гарантирует выход или возврат.
                raise RuntimeError("Unreachable")

            return async_wrapper  # type: ignore[return-value]
        else:
            @functools.wraps(func)
            def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
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
                raise RuntimeError("Unreachable")

            return sync_wrapper  # type: ignore[return-value]

    return decorator


def log_function_details(func: Callable[P, R]) -> Callable[P, R]:
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
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        _get_logger().devdebug("Вызов функции: %s() с аргументами %s и %s", func.__name__, args, kwargs)
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        end_time = time.perf_counter()
        run_time = end_time - start_time
        _get_logger().devdebug("Функция %s() завершилась за %.4f с. Результат: %s",
                               func.__name__, run_time, result)
        return result

    return wrapper


def timeout(seconds: float, fallback: Any = _NO_FALLBACK) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """
    Декоратор для ограничения времени выполнения функции.

    Поддерживает как синхронные, так и асинхронные функции.
    Для асинхронных функций использует `asyncio.wait_for`.
    Для синхронных функций запускает их в отдельном потоке и ожидает завершения.

    Args:
        seconds: Максимальное время выполнения в секундах.
        fallback: Значение, которое будет возвращено при таймауте.
            Если не указано, выбрасывается `ChutilsTimeoutError`.

    Returns:
        Декоратор функции.

    Raises:
        ChutilsTimeoutError: Если время выполнения превышено и `fallback` не указан.
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        if inspect.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> Union[R, Any]:
                try:
                    return await asyncio.wait_for(func(*args, **kwargs), timeout=seconds)  # type: ignore[no-any-return]
                except (asyncio.TimeoutError, TimeoutError):
                    if fallback is _NO_FALLBACK:
                        raise ChutilsTimeoutError(
                            f"Function {func.__name__} timed out after {seconds} seconds",
                            function=func.__name__,
                            timeout=seconds
                        )
                    return fallback

            return async_wrapper  # type: ignore[return-value]
        else:
            @functools.wraps(func)
            def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> Union[R, Any]:
                # Используем ThreadPoolExecutor для запуска в отдельном потоке
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(func, *args, **kwargs)
                    try:
                        return future.result(timeout=seconds)
                    except concurrent.futures.TimeoutError:
                        if fallback is _NO_FALLBACK:
                            raise ChutilsTimeoutError(
                                f"Function {func.__name__} timed out after {seconds} seconds",
                                function=func.__name__,
                                timeout=seconds
                            )
                        return fallback

            return sync_wrapper  # type: ignore[return-value]

    return decorator
