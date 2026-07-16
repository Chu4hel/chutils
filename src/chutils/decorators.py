"""
Модуль с полезными декораторами для автоматизации задач.

Включает инструменты для логирования производительности и деталей вызовов функций.
"""

import asyncio
import concurrent.futures
import functools
import inspect
import random
import threading
import time
from collections.abc import Callable, Awaitable
from typing import Optional, TYPE_CHECKING, Any, cast

from .exceptions import ChutilsTimeoutError
from .typing import P, R

if TYPE_CHECKING:
    from .logger import ChutilsLogger

# Уникальный маркер для определения, был ли передан fallback (позволяет передавать None)
_NO_FALLBACK = object()

# Ленивая инициализация логгера
_module_logger: Optional["ChutilsLogger"] = None


def _get_logger() -> "ChutilsLogger":
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
        exceptions: tuple[type[Exception], ...] = (Exception,),
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
                        return await cast(Awaitable[R], func(*args, **kwargs))
                    except exceptions as e:
                        if i == retries:
                            raise

                        _get_logger().warning(
                            "Попытка %d/%d завершилась ошибкой: %s. Повтор через %.2f с...",
                            i + 1,
                            retries,
                            e,
                            current_delay,
                        )

                        sleep_time = current_delay
                        if jitter:
                            sleep_time += random.uniform(0, 0.1 * current_delay)

                        await asyncio.sleep(sleep_time)
                        current_delay *= backoff
                # MyPy может ругаться, что не все пути возвращают значение,
                # но raise в цикле гарантирует выход или возврат.
                raise RuntimeError("Unreachable")

            return cast(Callable[..., Any], async_wrapper)
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
                            i + 1,
                            retries,
                            e,
                            current_delay,
                        )

                        sleep_time = current_delay
                        if jitter:
                            sleep_time += random.uniform(0, 0.1 * current_delay)

                        time.sleep(sleep_time)
                        current_delay *= backoff
                raise RuntimeError("Unreachable")

            return sync_wrapper

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
        _get_logger().devdebug(
            "Вызов функции: %s() с аргументами %s и %s", func.__name__, args, kwargs
        )
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        end_time = time.perf_counter()
        run_time = end_time - start_time
        _get_logger().devdebug(
            "Функция %s() завершилась за %.4f с. Результат: %s",
            func.__name__,
            run_time,
            result,
        )
        return result

    return wrapper


def timeout(
        seconds: float, fallback: Any = _NO_FALLBACK
) -> Callable[[Callable[P, R]], Callable[P, R]]:
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
            async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> R | Any:
                try:
                    return cast(
                        R,
                        await asyncio.wait_for(
                            cast(Awaitable[R], func(*args, **kwargs)), timeout=seconds
                        ),
                    )
                except (asyncio.TimeoutError, TimeoutError):
                    if fallback is _NO_FALLBACK:
                        raise ChutilsTimeoutError(
                            f"Function {func.__name__} timed out after {seconds} seconds",
                            function=func.__name__,
                            timeout=seconds,
                        )
                    return fallback

            return cast(Callable[..., Any], async_wrapper)
        else:

            @functools.wraps(func)
            def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> R | Any:
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
                                timeout=seconds,
                            )
                        return fallback

            return sync_wrapper

    return decorator


class TokenBucket:
    """Алгоритм маркерной корзины (Token Bucket)."""

    def __init__(self, capacity: int, period: float) -> None:
        """Инициализирует маркерную корзину.

        Args:
            capacity: Максимальная вместимость корзины (количество токенов).
            period: Временной интервал в секундах, за который корзина полностью пополняется.
        """
        self.capacity = float(capacity)
        self.period = float(period)
        self.refill_rate = self.capacity / self.period
        self.tokens = self.capacity
        self.last_refill = time.monotonic()
        self.next_allowed_time = time.monotonic()
        self.lock = threading.Lock()

    def acquire(self, wait: bool = False) -> float | None:
        """Запрашивает получение токена из корзины.

        Args:
            wait: Флаг необходимости блокирующего ожидания, если токенов нет.

        Returns:
            Время ожидания в секундах, если необходимо подождать, 0.0 если токен получен сразу,
            или None, если токенов нет и wait=False.
        """
        with self.lock:
            now = time.monotonic()

            if now >= self.next_allowed_time:
                # Пополняем токены
                elapsed = now - self.last_refill
                self.last_refill = now
                self.tokens = min(
                    self.capacity, self.tokens + elapsed * self.refill_rate
                )

                if self.tokens >= 1.0:
                    self.tokens -= 1.0
                    return 0.0

                if not wait:
                    return None

                # Вычисляем время ожидания
                missing = 1.0 - self.tokens
                wait_time = missing / self.refill_rate
                self.tokens = 0.0
                self.next_allowed_time = now + wait_time
                self.last_refill = self.next_allowed_time
                return wait_time
            else:
                if not wait:
                    return None

                # Встаем в очередь за предыдущим запросом
                wait_time = self.next_allowed_time - now
                self.next_allowed_time += 1.0 / self.refill_rate
                self.last_refill = self.next_allowed_time
                return wait_time


class LeakyBucket:
    """Алгоритм дырявого ведра (Leaky Bucket)."""

    def __init__(self, capacity: int, period: float) -> None:
        """Инициализирует дырявое ведро.

        Args:
            capacity: Максимальная вместимость ведра (максимальный уровень воды).
            period: Временной интервал в секундах, за который ведро полностью опустошается.
        """
        self.capacity = float(capacity)
        self.period = float(period)
        self.leak_rate = self.capacity / self.period
        self.water_level = 0.0
        self.last_leak = time.monotonic()
        self.next_allowed_time = time.monotonic()
        self.lock = threading.Lock()

    def acquire(self, wait: bool = False) -> float | None:
        """Запрашивает добавление единицы воды в ведро.

        Args:
            wait: Флаг необходимости блокирующего ожидания до тех пор, пока уровень воды не спадет.

        Returns:
            Время ожидания в секундах, если необходимо подождать, 0.0 если вода добавлена сразу,
            или None, если ведро переполнено и wait=False.
        """
        with self.lock:
            now = time.monotonic()

            if now >= self.next_allowed_time:
                # Вытекание воды
                elapsed = now - self.last_leak
                self.last_leak = now
                self.water_level = max(0.0, self.water_level - elapsed * self.leak_rate)

                if self.water_level + 1.0 <= self.capacity:
                    self.water_level += 1.0
                    return 0.0

                if not wait:
                    return None

                # Вычисляем время ожидания до возможности добавить еще единицу воды
                excess = (self.water_level + 1.0) - self.capacity
                wait_time = excess / self.leak_rate
                self.water_level = self.capacity
                self.next_allowed_time = now + wait_time
                self.last_leak = self.next_allowed_time
                return wait_time
            else:
                if not wait:
                    return None

                # Встаем в очередь
                wait_time = self.next_allowed_time - now
                self.next_allowed_time += 1.0 / self.leak_rate
                self.last_leak = self.next_allowed_time
                return wait_time


# Глобальный реестр ограничителей частоты
_limiters: dict[str, TokenBucket | LeakyBucket] = {}
_limiters_lock = threading.Lock()


def get_limiter(
        key: str, max_calls: int, period: float, strategy: str = "token_bucket"
) -> TokenBucket | LeakyBucket:
    """Возвращает или создает ограничитель частоты по ключу.

    Args:
        key: Уникальный ключ для идентификации ограничителя.
        max_calls: Максимальное число вызовов за период.
        period: Временной интервал в секундах.
        strategy: Стратегия ограничения частоты ("token_bucket" или "leaky_bucket").

    Returns:
        Экземпляр ограничителя частоты (TokenBucket или LeakyBucket).
    """
    global _limiters
    with _limiters_lock:
        if key not in _limiters:
            if strategy == "leaky_bucket":
                _limiters[key] = LeakyBucket(max_calls, period)
            else:
                _limiters[key] = TokenBucket(max_calls, period)
        return _limiters[key]


def clear_limiters() -> None:
    """Очищает реестр ограничителей (для тестов)."""
    global _limiters
    with _limiters_lock:
        _limiters.clear()


def rate_limit(
        max_calls: int,
        period: float,
        strategy: str = "token_bucket",
        wait: bool = False,
        key_func: Callable[..., str] | None = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """
    Декоратор для ограничения частоты вызовов функции (Throttling).

    Args:
        max_calls: Максимальное количество вызовов в период.
        period: Период времени в секундах.
        strategy: Стратегия лимитирования ("token_bucket" или "leaky_bucket").
        wait: Если True, блокирует выполнение до появления токена.
              Если False, сразу выбрасывает RateLimitExceededError при превышении лимита.
        key_func: Кастомная функция для генерации ключа лимитирования на основе аргументов.

    Returns:
        Декоратор функции.
    """
    from .exceptions import RateLimitExceededError

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                if key_func is not None:
                    limit_key = key_func(*args, **kwargs)
                else:
                    limit_key = f"{func.__module__}.{func.__qualname__}"

                limiter = get_limiter(limit_key, max_calls, period, strategy)
                wait_time = limiter.acquire(wait=wait)

                if wait_time is None:
                    raise RateLimitExceededError(
                        f"Rate limit exceeded for function '{func.__name__}'",
                        function=func.__name__,
                        limit_key=limit_key,
                        max_calls=max_calls,
                        period=period,
                    )

                if wait_time > 0.0:
                    await asyncio.sleep(wait_time)

                return await cast(Awaitable[R], func(*args, **kwargs))

            return cast(Callable[..., Any], async_wrapper)
        else:

            @functools.wraps(func)
            def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                if key_func is not None:
                    limit_key = key_func(*args, **kwargs)
                else:
                    limit_key = f"{func.__module__}.{func.__qualname__}"

                limiter = get_limiter(limit_key, max_calls, period, strategy)
                wait_time = limiter.acquire(wait=wait)

                if wait_time is None:
                    raise RateLimitExceededError(
                        f"Rate limit exceeded for function '{func.__name__}'",
                        function=func.__name__,
                        limit_key=limit_key,
                        max_calls=max_calls,
                        period=period,
                    )

                if wait_time > 0.0:
                    time.sleep(wait_time)

                return func(*args, **kwargs)

            return sync_wrapper

    return decorator


class CircuitBreakerState:
    """Машина состояний для паттерна Circuit Breaker (Предохранитель)."""

    def __init__(
            self,
            failure_threshold: int,
            recovery_timeout: float,
            exceptions: tuple[type[Exception], ...],
            name: str,
    ) -> None:
        """Инициализирует состояние предохранителя (Circuit Breaker).

        Args:
            failure_threshold: Порог неудачных попыток для открытия цепи.
            recovery_timeout: Таймаут восстановления в секундах.
            exceptions: Исключения, расцениваемые как ошибки.
            name: Имя предохранителя (обычно имя декорируемой функции).
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.exceptions = exceptions
        self.name = name

        # Состояния: CLOSED, OPEN, HALF_OPEN
        self.state = "CLOSED"
        self.failure_count = 0
        self.last_failure_time = 0.0
        self._half_open_in_progress = False

        # Блокировка для обеспечения потокобезопасности
        self._lock = threading.Lock()

    def record_success(self) -> None:
        """Записывает успешное выполнение и сбрасывает состояние сбоев в CLOSED."""
        with self._lock:
            if self.state != "CLOSED":
                logger = _get_logger()
                logger.info(
                    "CircuitBreaker [%s]: цепь замкнута (CLOSED). Восстановление прошло успешно.",
                    self.name,
                )
            self.state = "CLOSED"
            self._half_open_in_progress = False
            self.failure_count = 0
            self.last_failure_time = 0.0
            self._report_metrics_state()

    def record_failure(self, exc: Exception) -> None:
        """Записывает неудачную попытку выполнения.

        Args:
            exc: Возникшее исключение.
        """
        if not isinstance(exc, self.exceptions):
            if self.state == "HALF_OPEN":
                with self._lock:
                    self._half_open_in_progress = False
            return

        with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()
            if self.state in ("CLOSED", "HALF_OPEN"):
                if (
                        self.state == "HALF_OPEN"
                        or self.failure_count >= self.failure_threshold
                ):
                    logger = _get_logger()
                    logger.warning(
                        "CircuitBreaker [%s]: цепь разомкнута (OPEN). Ошибка: %s: %s. Блокировка на %s сек.",
                        self.name,
                        type(exc).__name__,
                        exc,
                        self.recovery_timeout,
                    )
                    self.state = "OPEN"
                    self._report_metrics_state()
            self._half_open_in_progress = False

    def _report_metrics_state(self) -> None:
        """Экспортирует текущее состояние предохранителя в модуль метрик.
        CLOSED = 0, OPEN = 1, HALF_OPEN = 2.
        """
        try:
            from chutils.metrics import set_gauge
            state_val = 0.0
            if self.state == "OPEN":
                state_val = 1.0
            elif self.state == "HALF_OPEN":
                state_val = 2.0
            set_gauge("circuit_breaker_state", state_val, labels={"name": self.name})
        except Exception:
            # Игнорируем ошибки при отправке метрик, чтобы не ломать логику предохранителя
            pass

    def can_execute(self) -> bool:
        """Проверяет возможность выполнения операции в текущем состоянии цепи.

        Returns:
            True, если выполнение разрешено, иначе False.
        """
        with self._lock:
            if self.state == "CLOSED":
                return True
            now = time.time()
            if self.state == "OPEN":
                if now - self.last_failure_time >= self.recovery_timeout:
                    self.state = "HALF_OPEN"
                    self._half_open_in_progress = True
                    self._report_metrics_state()
                    return True
                return False
            if self.state == "HALF_OPEN":
                if self._half_open_in_progress:
                    return False
                self._half_open_in_progress = True
                return True
            return False


def circuit_breaker(
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Декоратор Circuit Breaker (Предохранитель) для защиты от каскадных сбоев.

    Args:
        failure_threshold: Количество последовательных ошибок для открытия цепи.
        recovery_timeout: Время в секундах, в течение которого цепь остается открытой.
        exceptions: Кортеж исключений, которые считаются ошибками.

    Returns:
        Декоратор, оборачивающий функцию механизмом автоматического отключения при сбоях.
    """
    from .exceptions import CircuitBreakerOpenError

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        name = func.__name__
        state = CircuitBreakerState(
            failure_threshold, recovery_timeout, exceptions, name
        )

        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> Any:
                if not state.can_execute():
                    raise CircuitBreakerOpenError(
                        f"CircuitBreaker [{name}] is OPEN. Requests blocked."
                    )
                try:
                    res = await func(*args, **kwargs)
                    state.record_success()
                    return res
                except Exception as e:
                    state.record_failure(e)
                    raise e

            return cast(Callable[P, R], async_wrapper)
        else:

            @functools.wraps(func)
            def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                if not state.can_execute():
                    raise CircuitBreakerOpenError(
                        f"CircuitBreaker [{name}] is OPEN. Requests blocked."
                    )
                try:
                    res = func(*args, **kwargs)
                    state.record_success()
                    return res
                except Exception as e:
                    state.record_failure(e)
                    raise e

            return sync_wrapper

    return decorator
