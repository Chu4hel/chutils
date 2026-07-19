"""
Тесты для модуля chutils.http.resilience.

Проверяет применение `ResiliencePolicy` к произвольным вызовам функций:
- retry при временных ошибках и 5xx-статусах
- timeout при превышении времени
- semaphore для ограничения конкурентности
- circuit_breaker при накоплении ошибок
"""
from __future__ import annotations

import asyncio
import threading
import time
from unittest.mock import patch

import pytest

from chutils.http.resilience import ResiliencePolicy


# ─── Вспомогательные fixture ────────────────────────────────────────────────


class _TransientError(Exception):
    """Временная ошибка для тестов retry."""


class _HttpError(Exception):
    """HTTP-ошибка с кодом статуса."""

    def __init__(self, status_code: int) -> None:
        super().__init__(f"HTTP {status_code}")
        self.status_code = status_code


# ─── ResiliencePolicy: базовые тесты ────────────────────────────────────────


def test_policy_default_values() -> None:
    """Проверяет значения по умолчанию ResiliencePolicy."""
    policy = ResiliencePolicy()
    assert policy.retries == 3
    assert policy.retry_delay == 0.5
    assert policy.retry_backoff == 2.0
    assert policy.retry_jitter is False
    assert policy.timeout is None
    assert policy.max_concurrency is None
    assert policy.cb_failure_threshold == 5
    assert policy.cb_recovery_timeout == 30.0


def test_policy_custom_values() -> None:
    """Проверяет кастомные значения ResiliencePolicy."""
    policy = ResiliencePolicy(
        retries=5,
        retry_delay=0.1,
        retry_backoff=1.5,
        retry_jitter=True,
        timeout=10.0,
        max_concurrency=3,
        cb_failure_threshold=2,
        cb_recovery_timeout=60.0,
    )
    assert policy.retries == 5
    assert policy.retry_delay == 0.1
    assert policy.retry_backoff == 1.5
    assert policy.retry_jitter is True
    assert policy.timeout == 10.0
    assert policy.max_concurrency == 3
    assert policy.cb_failure_threshold == 2
    assert policy.cb_recovery_timeout == 60.0


# ─── ResiliencePolicy.apply_sync: retry ──────────────────────────────────────


def test_apply_sync_success_on_first_attempt() -> None:
    """Успешный вызов без повторов."""
    policy = ResiliencePolicy(retries=3, retry_delay=0.0)
    call_count = 0

    def func() -> str:
        nonlocal call_count
        call_count += 1
        return "ok"

    result = policy.apply_sync(func)
    assert result == "ok"
    assert call_count == 1


def test_apply_sync_retry_on_transient_error() -> None:
    """Повтор при временной ошибке, успех на 3-й попытке."""
    policy = ResiliencePolicy(retries=3, retry_delay=0.0, retry_exceptions=(_TransientError,))
    call_count = 0

    def func() -> str:
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise _TransientError("временная")
        return "recovered"

    result = policy.apply_sync(func)
    assert result == "recovered"
    assert call_count == 3


def test_apply_sync_exhausts_retries() -> None:
    """После исчерпания попыток пробрасывает последнее исключение."""
    policy = ResiliencePolicy(retries=2, retry_delay=0.0, retry_exceptions=(_TransientError,))
    call_count = 0

    def func() -> str:
        nonlocal call_count
        call_count += 1
        raise _TransientError("permanent")

    with pytest.raises(_TransientError):
        policy.apply_sync(func)

    assert call_count == 3  # 1 initial + 2 retries


def test_apply_sync_no_retry_on_non_matching_exception() -> None:
    """Не повторяет при исключении, не входящем в retry_exceptions."""
    policy = ResiliencePolicy(retries=3, retry_delay=0.0, retry_exceptions=(_TransientError,))
    call_count = 0

    def func() -> str:
        nonlocal call_count
        call_count += 1
        raise ValueError("другая ошибка")

    with pytest.raises(ValueError):
        policy.apply_sync(func)

    assert call_count == 1


def test_apply_sync_retry_on_5xx_status() -> None:
    """Повтор при 5xx статусе HTTP."""
    policy = ResiliencePolicy(retries=2, retry_delay=0.0, retry_on_status_codes=(500, 503))
    call_count = 0

    def func() -> str:
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise _HttpError(503)
        return "ok"

    result = policy.apply_sync(func, http_error_extractor=lambda e: e.status_code)  # type: ignore[attr-defined]
    assert result == "ok"
    assert call_count == 3


def test_apply_sync_backoff_between_retries() -> None:
    """Проверяет, что задержка увеличивается с backoff."""
    policy = ResiliencePolicy(retries=2, retry_delay=0.1, retry_backoff=2.0, retry_exceptions=(_TransientError,))
    sleep_calls: list[float] = []

    original_sleep = time.sleep

    def mock_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)
        # Не спим по-настоящему в тесте
        pass  # noqa: PIE790

    def func() -> str:
        raise _TransientError("fail")

    with patch("time.sleep", side_effect=mock_sleep):
        with pytest.raises(_TransientError):
            policy.apply_sync(func)

    # Задержки: 0.1, 0.2 (backoff=2.0)
    assert len(sleep_calls) == 2
    assert sleep_calls[0] == pytest.approx(0.1, abs=0.01)
    assert sleep_calls[1] == pytest.approx(0.2, abs=0.01)


# ─── ResiliencePolicy.apply_sync: timeout ────────────────────────────────────


def test_apply_sync_timeout_raises() -> None:
    """Превышение timeout вызывает ChutilsTimeoutError."""
    from chutils.exceptions import ChutilsTimeoutError

    policy = ResiliencePolicy(retries=0, timeout=0.05)

    def slow_func() -> str:
        time.sleep(1.0)
        return "never"

    with pytest.raises(ChutilsTimeoutError):
        policy.apply_sync(slow_func)


def test_apply_sync_timeout_ok_within_limit() -> None:
    """Функция укладывается в timeout, исключений нет."""
    policy = ResiliencePolicy(retries=0, timeout=5.0)

    def fast_func() -> str:
        return "fast"

    result = policy.apply_sync(fast_func)
    assert result == "fast"


# ─── ResiliencePolicy.apply_sync: semaphore (max_concurrency) ────────────────


def test_apply_sync_semaphore_limits_concurrency() -> None:
    """Семафор не позволяет выполнять больше max_concurrency вызовов одновременно."""
    policy = ResiliencePolicy(retries=0, max_concurrency=2)
    active_count = 0
    max_active = 0
    lock = threading.Lock()
    results: list[str] = []

    def func() -> str:
        nonlocal active_count, max_active
        with lock:
            active_count += 1
            if active_count > max_active:
                max_active = active_count
        time.sleep(0.05)
        with lock:
            active_count -= 1
        return "done"

    threads = [
        threading.Thread(target=lambda: results.append(policy.apply_sync(func)))
        for _ in range(5)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert max_active <= 2
    assert len(results) == 5


# ─── ResiliencePolicy.apply_async: retry ─────────────────────────────────────


@pytest.mark.asyncio
async def test_apply_async_success_on_first_attempt() -> None:
    """Успешный async-вызов без повторов."""
    policy = ResiliencePolicy(retries=3, retry_delay=0.0)
    call_count = 0

    async def func() -> str:
        nonlocal call_count
        call_count += 1
        return "async_ok"

    result = await policy.apply_async(func)
    assert result == "async_ok"
    assert call_count == 1


@pytest.mark.asyncio
async def test_apply_async_retry_on_transient_error() -> None:
    """Async: повтор при временной ошибке."""
    policy = ResiliencePolicy(retries=2, retry_delay=0.0, retry_exceptions=(_TransientError,))
    call_count = 0

    async def func() -> str:
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise _TransientError("async transient")
        return "async_recovered"

    result = await policy.apply_async(func)
    assert result == "async_recovered"
    assert call_count == 3


@pytest.mark.asyncio
async def test_apply_async_exhausts_retries() -> None:
    """Async: после исчерпания попыток пробрасывает исключение."""
    policy = ResiliencePolicy(retries=1, retry_delay=0.0, retry_exceptions=(_TransientError,))

    async def func() -> str:
        raise _TransientError("always fails")

    with pytest.raises(_TransientError):
        await policy.apply_async(func)


@pytest.mark.asyncio
async def test_apply_async_timeout_raises() -> None:
    """Async: превышение timeout вызывает ChutilsTimeoutError."""
    from chutils.exceptions import ChutilsTimeoutError

    policy = ResiliencePolicy(retries=0, timeout=0.05)

    async def slow_func() -> str:
        await asyncio.sleep(5.0)
        return "never"

    with pytest.raises(ChutilsTimeoutError):
        await policy.apply_async(slow_func)


@pytest.mark.asyncio
async def test_apply_async_semaphore_limits_concurrency() -> None:
    """Async: семафор ограничивает конкурентные вызовы."""
    policy = ResiliencePolicy(retries=0, max_concurrency=2)
    active_count = 0
    max_active = 0

    async def func() -> str:
        nonlocal active_count, max_active
        active_count += 1
        if active_count > max_active:
            max_active = active_count
        await asyncio.sleep(0.05)
        active_count -= 1
        return "done"

    tasks = [policy.apply_async(func) for _ in range(6)]
    await asyncio.gather(*tasks)

    assert max_active <= 2
