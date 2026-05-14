import asyncio
import time

import pytest

from chutils.decorators import timeout


# --- Sync Tests ---

def test_timeout_sync_success():
    """Проверяет успешное выполнение быстрой синхронной функции."""

    @timeout(0.5)
    def quick_func():
        return "success"

    assert quick_func() == "success"


def test_timeout_sync_failure():
    """Проверяет выброс TimeoutError для долгой синхронной функции."""

    @timeout(0.1)
    def slow_func():
        time.sleep(0.3)
        return "too slow"

    with pytest.raises(TimeoutError):
        slow_func()


def test_timeout_sync_fallback():
    """Проверяет возврат fallback значения для синхронной функции."""

    @timeout(0.1, fallback="fallback_value")
    def slow_func():
        time.sleep(0.3)
        return "too slow"

    assert slow_func() == "fallback_value"


def test_timeout_sync_fallback_none():
    """Проверяет возврат None как легитимного fallback значения."""

    @timeout(0.1, fallback=None)
    def slow_func():
        time.sleep(0.3)
        return "too slow"

    assert slow_func() is None


# --- Async Tests ---

@pytest.mark.asyncio
async def test_timeout_async_success():
    """Проверяет успешное выполнение быстрой асинхронной функции."""

    @timeout(0.5)
    async def quick_async_func():
        await asyncio.sleep(0.1)
        return "async success"

    result = await quick_async_func()
    assert result == "async success"


@pytest.mark.asyncio
async def test_timeout_async_failure():
    """Проверяет выброс TimeoutError для долгой асинхронной функции."""

    @timeout(0.1)
    async def slow_async_func():
        await asyncio.sleep(0.3)
        return "too slow"

    with pytest.raises(TimeoutError):
        await slow_async_func()


@pytest.mark.asyncio
async def test_timeout_async_fallback():
    """Проверяет возврат fallback значения для асинхронной функции."""

    @timeout(0.1, fallback="async_fallback")
    async def slow_async_func():
        await asyncio.sleep(0.3)
        return "too slow"

    result = await slow_async_func()
    assert result == "async_fallback"


@pytest.mark.asyncio
async def test_timeout_async_fallback_none():
    """Проверяет возврат None как fallback значения для асинхронной функции."""

    @timeout(0.1, fallback=None)
    async def slow_async_func():
        await asyncio.sleep(0.3)
        return "too slow"

    result = await slow_async_func()
    assert result is None
