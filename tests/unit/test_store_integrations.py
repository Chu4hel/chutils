"""
Юнит-тесты для сквозных интеграций chutils.store (трассировка, метрики, декоратор кэша).
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from chutils.store.backends.memory import MemoryStore
from chutils.store.decorator import store_cache
from chutils.store.manager import StoreManager


def test_store_manager_metrics_and_tracing_hooks() -> None:
    """Проверяет вызов хуков метрик и трассировки при операциях get/set."""
    mock_tracer = MagicMock()
    mock_metrics = MagicMock()

    with patch("chutils.store.manager._get_tracing", return_value=mock_tracer), patch(
        "chutils.store.manager._get_metrics", return_value=mock_metrics
    ):
        manager = StoreManager(backend=MemoryStore())

        manager.set("k1", "v1")
        assert manager.get("k1") == "v1"
        assert manager.get("missing") is None

        # Проверяем вызов трассировки и метрик
        assert mock_tracer.trace.call_count >= 3


def test_store_cache_decorator_sync() -> None:
    """Проверяет синхронный декоратор @store_cache с использованием StoreManager."""
    manager = StoreManager(backend=MemoryStore())
    call_count = 0

    @store_cache(store=manager, ttl=60)
    def compute(x: int) -> int:
        nonlocal call_count
        call_count += 1
        return x * 2

    assert compute(5) == 10
    assert call_count == 1

    # Вторым вызовом берется из кэша
    assert compute(5) == 10
    assert call_count == 1

    # Инвалидация
    compute.invalidate(5)
    assert compute(5) == 10
    assert call_count == 2


@pytest.mark.asyncio
async def test_store_cache_decorator_async() -> None:
    """Проверяет асинхронный декоратор @store_cache с использованием StoreManager."""
    manager = StoreManager(backend=MemoryStore())
    call_count = 0

    @store_cache(store=manager, ttl=60)
    async def async_compute(x: int) -> int:
        nonlocal call_count
        call_count += 1
        return x * 3

    res1 = await async_compute(4)
    assert res1 == 12
    assert call_count == 1

    res2 = await async_compute(4)
    assert res2 == 12
    assert call_count == 1

    # Инвалидация
    await async_compute.ainvalidate(4)
    res3 = await async_compute(4)
    assert res3 == 12
    assert call_count == 2
