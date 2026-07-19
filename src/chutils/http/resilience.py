"""
Модуль chutils.http.resilience — Политика отказоустойчивости для HTTP-клиента.

Предоставляет класс `ResiliencePolicy`, который инкапсулирует настройки
retry, timeout, semaphore (max_concurrency) и circuit_breaker,
а также методы `apply_sync` и `apply_async` для применения этих политик
к произвольным вызываемым объектам.
"""
from __future__ import annotations

import asyncio
import random
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from chutils.logger import ChutilsLogger

_module_logger: Optional["ChutilsLogger"] = None


def _get_log() -> "ChutilsLogger":
    """Возвращает лениво инициализированный логгер модуля."""
    global _module_logger
    if _module_logger is None:
        from chutils import logger as chutils_logger
        _module_logger = chutils_logger.setup_logger(__name__)
    if _module_logger is None:
        raise RuntimeError("Не удалось инициализировать логгер chutils.http.resilience")
    return _module_logger

# Значение-маркер: статус-код ещё не извлечён
_UNSET = object()


# ─── Исключения resilience ────────────────────────────────────────────────────


class _CircuitOpenError(Exception):
    """Circuit Breaker открыт — запросы временно заблокированы."""


# ─── Состояние Circuit Breaker ────────────────────────────────────────────────


@dataclass
class _CircuitBreakerState:
    """Потокобезопасное состояние Circuit Breaker."""

    failure_threshold: int
    recovery_timeout: float

    _failure_count: int = field(default=0, init=False, repr=False)
    _opened_at: float | None = field(default=None, init=False, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    @property
    def is_open(self) -> bool:
        """Возвращает True, если цепь разомкнута (запросы блокируются)."""
        with self._lock:
            if self._opened_at is None:
                return False
            if time.monotonic() - self._opened_at >= self.recovery_timeout:
                # Время восстановления истекло — переходим в half-open
                self._opened_at = None
                self._failure_count = 0
                return False
            return True

    def record_failure(self) -> None:
        """Фиксирует отказ; размыкает цепь при достижении порога."""
        with self._lock:
            self._failure_count += 1
            if self._failure_count >= self.failure_threshold:
                self._opened_at = time.monotonic()
                _get_log().warning(
                    "Circuit Breaker открыт после %d отказов. "
                    "Восстановление через %.1f сек.",
                    self._failure_count,
                    self.recovery_timeout,
                )

    def record_success(self) -> None:
        """Фиксирует успех; сбрасывает счётчик ошибок."""
        with self._lock:
            self._failure_count = 0
            self._opened_at = None


# ─── ResiliencePolicy ─────────────────────────────────────────────────────────


class ResiliencePolicy:
    """Политика отказоустойчивости: retry, timeout, semaphore, circuit breaker.

    Применяется к произвольным синхронным (`apply_sync`) и асинхронным
    (`apply_async`) вызовам для обеспечения надёжности.

    Attributes:
        retries: Количество повторных попыток после первого отказа.
        retry_delay: Базовая задержка (сек.) между попытками.
        retry_backoff: Множитель задержки для экспоненциального отступа.
        retry_jitter: Добавлять ли случайный шум к задержке.
        retry_exceptions: Кортеж классов исключений, при которых выполняется повтор.
        retry_on_status_codes: Набор HTTP-статус-кодов, при которых выполняется повтор.
        timeout: Максимальное время выполнения вызова (сек.); None — без ограничения.
        max_concurrency: Максимальное число одновременных вызовов; None — без ограничения.
        cb_failure_threshold: Порог отказов для размыкания Circuit Breaker.
        cb_recovery_timeout: Время (сек.) до попытки восстановления Circuit Breaker.

    Example:
        ```python
        policy = ResiliencePolicy(retries=3, timeout=5.0, max_concurrency=10)
        result = policy.apply_sync(requests.get, url)
        ```
    """

    def __init__(
            self,
            *,
            retries: int = 3,
            retry_delay: float = 0.5,
            retry_backoff: float = 2.0,
            retry_jitter: bool = False,
            retry_exceptions: tuple[type[Exception], ...] = (Exception,),
            retry_on_status_codes: tuple[int, ...] = (429, 500, 502, 503, 504),
            timeout: float | None = None,
            max_concurrency: int | None = None,
            cb_failure_threshold: int = 5,
            cb_recovery_timeout: float = 30.0,
    ) -> None:
        """Инициализирует политику отказоустойчивости.

        Args:
            retries: Количество повторных попыток после первого отказа.
            retry_delay: Базовая задержка между попытками в секундах.
            retry_backoff: Множитель задержки для экспоненциального отступа.
            retry_jitter: Если True, добавляет случайный шум к задержке.
            retry_exceptions: Кортеж классов исключений, при которых выполняется retry.
            retry_on_status_codes: HTTP-статус-коды для retry (используется с extractor).
            timeout: Максимальное время выполнения вызова в секундах.
            max_concurrency: Максимальное число одновременных вызовов.
            cb_failure_threshold: Порог отказов для открытия Circuit Breaker.
            cb_recovery_timeout: Пауза перед попыткой восстановления Circuit Breaker.
        """
        self.retries = retries
        self.retry_delay = retry_delay
        self.retry_backoff = retry_backoff
        self.retry_jitter = retry_jitter
        self.retry_exceptions = retry_exceptions
        self.retry_on_status_codes = set(retry_on_status_codes)
        self.timeout = timeout
        self.max_concurrency = max_concurrency
        self.cb_failure_threshold = cb_failure_threshold
        self.cb_recovery_timeout = cb_recovery_timeout

        # Синхронный семафор
        self._semaphore: threading.Semaphore | None = (
            threading.Semaphore(max_concurrency) if max_concurrency is not None else None
        )
        # Асинхронный семафор создаётся лениво (в event loop)
        self._async_semaphore: asyncio.Semaphore | None = None

        # Circuit Breaker
        self._cb_state = _CircuitBreakerState(
            failure_threshold=cb_failure_threshold,
            recovery_timeout=cb_recovery_timeout,
        )

    # ─── Внутренние хелперы ────────────────────────────────────────────────

    def _get_async_semaphore(self) -> asyncio.Semaphore | None:
        """Лениво создаёт asyncio.Semaphore при первом async-вызове.

        Returns:
            Экземпляр asyncio.Semaphore или None, если ограничение не задано.
        """
        if self.max_concurrency is None:
            return None
        if self._async_semaphore is None:
            self._async_semaphore = asyncio.Semaphore(self.max_concurrency)
        return self._async_semaphore

    def _should_retry_exception(
            self,
            exc: Exception,
            http_error_extractor: Callable[[Exception], int] | None,
    ) -> bool:
        """Определяет, нужен ли повтор для данного исключения.

        Args:
            exc: Перехваченное исключение.
            http_error_extractor: Функция извлечения HTTP-статус-кода из исключения.

        Returns:
            True, если повтор необходим.
        """
        # Проверяем HTTP-статус-коды (приоритет перед классами исключений)
        if http_error_extractor is not None:
            try:
                code = http_error_extractor(exc)
                if code in self.retry_on_status_codes:
                    return True
            except Exception:  # noqa: BLE001
                pass

        return isinstance(exc, self.retry_exceptions)

    def _compute_delay(self, attempt: int, base_delay: float) -> float:
        """Вычисляет задержку перед следующей попыткой.

        Args:
            attempt: Номер текущей попытки (0-based).
            base_delay: Базовая задержка в секундах.

        Returns:
            Задержка в секундах.
        """
        delay = base_delay * (self.retry_backoff ** attempt)
        if self.retry_jitter:
            delay *= random.uniform(0.5, 1.5)  # noqa: S311
        return delay

    # ─── apply_sync ────────────────────────────────────────────────────────

    def apply_sync(
            self,
            func: Callable[..., object],
            *args: object,
            http_error_extractor: Callable[[Exception], int] | None = None,
            **kwargs: object,
    ) -> object:
        """Применяет политику к синхронному вызову.

        Оборачивает `func(*args, **kwargs)` в retry, timeout и semaphore.

        Args:
            func: Вызываемый объект.
            *args: Позиционные аргументы для `func`.
            http_error_extractor: Опциональная функция для извлечения
                HTTP-статус-кода из пойманного исключения. Используется
                для retry по `retry_on_status_codes`.
            **kwargs: Именованные аргументы для `func`.

        Returns:
            Результат `func(*args, **kwargs)`.

        Raises:
            ChutilsTimeoutError: При превышении `timeout`.
            CircuitBreakerOpenError: Если Circuit Breaker разомкнут.
            Exception: Последнее перехваченное исключение после исчерпания retry.
        """
        from chutils.exceptions import ChutilsTimeoutError, CircuitBreakerOpenError

        if self._cb_state.is_open:
            raise CircuitBreakerOpenError(
                "Circuit Breaker открыт. Запросы временно заблокированы."
            )

        last_exc: Exception | None = None

        for attempt in range(self.retries + 1):
            sem = self._semaphore

            def _call() -> object:
                if sem is not None:
                    sem.acquire()
                try:
                    return func(*args, **kwargs)
                finally:
                    if sem is not None:
                        sem.release()

            try:
                if self.timeout is not None:
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                        future = ex.submit(_call)
                        try:
                            result = future.result(timeout=self.timeout)
                        except concurrent.futures.TimeoutError:
                            raise ChutilsTimeoutError(
                                f"Вызов превысил timeout={self.timeout}с.",
                                timeout=self.timeout,
                            )
                else:
                    result = _call()

                self._cb_state.record_success()
                return result

            except ChutilsTimeoutError:
                self._cb_state.record_failure()
                raise
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                self._cb_state.record_failure()

                if attempt < self.retries and self._should_retry_exception(exc, http_error_extractor):
                    delay = self._compute_delay(attempt, self.retry_delay)
                    _get_log().debug(
                        "Попытка %d/%d не удалась (%s). Повтор через %.2f сек.",
                        attempt + 1,
                        self.retries + 1,
                        type(exc).__name__,
                        delay,
                    )
                    time.sleep(delay)
                    continue

                raise

        # Этот код недостижим, но удовлетворяет type checker
        assert last_exc is not None  # noqa: S101
        raise last_exc

    # ─── apply_async ───────────────────────────────────────────────────────

    async def apply_async(
            self,
            func: Callable[..., object],
            *args: object,
            http_error_extractor: Callable[[Exception], int] | None = None,
            **kwargs: object,
    ) -> object:
        """Применяет политику к асинхронному вызову.

        Оборачивает `await func(*args, **kwargs)` в retry, timeout и semaphore.

        Args:
            func: Асинхронный вызываемый объект (coroutine function).
            *args: Позиционные аргументы для `func`.
            http_error_extractor: Опциональная функция для извлечения
                HTTP-статус-кода из пойманного исключения.
            **kwargs: Именованные аргументы для `func`.

        Returns:
            Результат `await func(*args, **kwargs)`.

        Raises:
            ChutilsTimeoutError: При превышении `timeout`.
            CircuitBreakerOpenError: Если Circuit Breaker разомкнут.
            Exception: Последнее перехваченное исключение после исчерпания retry.
        """
        from chutils.exceptions import ChutilsTimeoutError, CircuitBreakerOpenError

        if self._cb_state.is_open:
            raise CircuitBreakerOpenError(
                "Circuit Breaker открыт. Запросы временно заблокированы."
            )

        sem = self._get_async_semaphore()
        last_exc: Exception | None = None

        for attempt in range(self.retries + 1):
            async def _call() -> object:
                if sem is not None:
                    async with sem:
                        return await func(*args, **kwargs)  # type: ignore[misc]
                return await func(*args, **kwargs)  # type: ignore[misc]

            try:
                if self.timeout is not None:
                    try:
                        result = await asyncio.wait_for(_call(), timeout=self.timeout)
                    except asyncio.TimeoutError:
                        raise ChutilsTimeoutError(
                            f"Async-вызов превысил timeout={self.timeout}с.",
                            timeout=self.timeout,
                        )
                else:
                    result = await _call()

                self._cb_state.record_success()
                return result

            except ChutilsTimeoutError:
                self._cb_state.record_failure()
                raise
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                self._cb_state.record_failure()

                if attempt < self.retries and self._should_retry_exception(exc, http_error_extractor):
                    delay = self._compute_delay(attempt, self.retry_delay)
                    _get_log().debug(
                        "Async попытка %d/%d не удалась (%s). Повтор через %.2f сек.",
                        attempt + 1,
                        self.retries + 1,
                        type(exc).__name__,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    continue

                raise

        assert last_exc is not None  # noqa: S101
        raise last_exc
