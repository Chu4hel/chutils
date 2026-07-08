"""Тесты для декоратора circuit_breaker."""
import asyncio
import threading
import time

import pytest

from chutils.decorators import circuit_breaker
from chutils.exceptions import CircuitBreakerOpenError


def test_sync_circuit_breaker_full_cycle(mocker):
    """Проверяет полный цикл состояний CLOSED -> OPEN -> HALF_OPEN -> CLOSED (sync)."""
    should_fail = True
    call_count = 0

    @circuit_breaker(failure_threshold=2, recovery_timeout=5)
    def target():
        nonlocal call_count
        call_count += 1
        if should_fail:
            raise ValueError("fail")
        return "ok"

    # CLOSED state
    with pytest.raises(ValueError):
        target()
    with pytest.raises(ValueError):
        target()

    assert call_count == 2

    # OPEN state (запросы блокируются)
    with pytest.raises(CircuitBreakerOpenError):
        target()

    assert call_count == 2

    # Эмулируем прохождение времени (переход в HALF_OPEN)
    now = time.time()
    mocker.patch("time.time", return_value=now + 6)

    # В HALF_OPEN запросу разрешено выполниться. Пусть он завершится успешно.
    should_fail = False
    assert target() == "ok"
    assert call_count == 3

    # Цепь должна замкнуться (CLOSED). Следующие вызовы проходят нормально.
    assert target() == "ok"
    assert call_count == 4


def test_sync_circuit_breaker_half_open_failure_reopens(mocker):
    """Проверяет, что при сбое в HALF_OPEN цепь возвращается в OPEN."""
    should_fail = True
    call_count = 0

    @circuit_breaker(failure_threshold=2, recovery_timeout=5)
    def target():
        nonlocal call_count
        call_count += 1
        if should_fail:
            raise ValueError("fail")
        return "ok"

    # Переводим в OPEN
    with pytest.raises(ValueError):
        target()
    with pytest.raises(ValueError):
        target()

    # Проверяем блокировку
    with pytest.raises(CircuitBreakerOpenError):
        target()

    # Истек таймаут восстановления
    now = time.time()
    mocker.patch("time.time", return_value=now + 6)

    # Запрос в HALF_OPEN падает
    with pytest.raises(ValueError):
        target()
    assert call_count == 3

    # Цепь снова в OPEN, запросы блокируются
    with pytest.raises(CircuitBreakerOpenError):
        target()
    assert call_count == 3


@pytest.mark.asyncio
async def test_async_circuit_breaker_full_cycle(mocker):
    """Проверяет полный цикл состояний для асинхронной функции."""
    should_fail = True
    call_count = 0

    @circuit_breaker(failure_threshold=2, recovery_timeout=5)
    async def target():
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.001)
        if should_fail:
            raise ValueError("fail")
        return "ok"

    with pytest.raises(ValueError):
        await target()
    with pytest.raises(ValueError):
        await target()

    assert call_count == 2

    with pytest.raises(CircuitBreakerOpenError):
        await target()

    now = time.time()
    mocker.patch("time.time", return_value=now + 6)

    should_fail = False
    assert await target() == "ok"
    assert call_count == 3
    assert await target() == "ok"
    assert call_count == 4


def test_circuit_breaker_thread_safety():
    """Проверяет потокобезопасность при параллельных вызовах в разных потоках."""
    call_count = 0
    lock = threading.Lock()

    @circuit_breaker(failure_threshold=100, recovery_timeout=5)
    def target():
        nonlocal call_count
        with lock:
            call_count += 1
        time.sleep(0.005)
        return "ok"

    threads = []
    for _ in range(10):
        t = threading.Thread(target=target)
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    assert call_count == 10


@pytest.mark.asyncio
async def test_circuit_breaker_async_concurrency():
    """Проверяет конкурентные вызовы в asyncio (gather)."""
    call_count = 0

    @circuit_breaker(failure_threshold=100, recovery_timeout=5)
    async def target():
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.005)
        return "ok"

    results = await asyncio.gather(
        target(), target(), target(), target(), target()
    )
    assert results == ["ok"] * 5
    assert call_count == 5


def test_circuit_breaker_exceptions_filter():
    """Проверяет, что цепь реагирует только на исключения, переданные в exceptions."""
    call_count = 0

    @circuit_breaker(failure_threshold=2, recovery_timeout=5, exceptions=(TypeError,))
    def target():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise ValueError("not tracked")
        if call_count == 2:
            raise TypeError("tracked")
        return "ok"

    # Сбой с ValueError не увеличивает счетчик сбоев до порога
    with pytest.raises(ValueError):
        target()

    # Сбой с TypeError 1
    with pytest.raises(TypeError):
        target()

    # Цепь все еще закрыта, так как TypeError был только 1, а ValueError проигнорирован
    assert target() == "ok"
