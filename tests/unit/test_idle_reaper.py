"""Модульные тесты для сторожевого таймера неактивности IdleBrowserReaper (Scale-to-Zero)."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock

import pytest

from chutils import (
    IdleBrowserReaper,
    IdleBrowserReaperConfig,
    IdleReaper,
    IdleReaperConfig,
)
from chutils.scraping import (
    IdleBrowserReaper as ScrapingIdleBrowserReaper,
)
from chutils.scraping import (
    IdleBrowserReaperConfig as ScrapingIdleBrowserReaperConfig,
)
from chutils.scraping.concurrency import (
    IdleBrowserReaper as ConcurrencyIdleBrowserReaper,
)
from chutils.scraping.concurrency import (
    IdleBrowserReaperConfig as ConcurrencyIdleBrowserReaperConfig,
)
from chutils.scraping.nodriver import (
    IdleBrowserReaper as NodriverIdleBrowserReaper,
)
from chutils.scraping.nodriver import (
    IdleBrowserReaperConfig as NodriverIdleBrowserReaperConfig,
)


def test_idle_reaper_imports() -> None:
    """Проверяет корректность экспорта IdleBrowserReaper, IdleReaper и их конфигов."""
    assert IdleBrowserReaper is ConcurrencyIdleBrowserReaper
    assert IdleReaper is IdleBrowserReaper
    assert ScrapingIdleBrowserReaper is IdleBrowserReaper
    assert NodriverIdleBrowserReaper is IdleBrowserReaper

    assert IdleBrowserReaperConfig is ConcurrencyIdleBrowserReaperConfig
    assert IdleReaperConfig is IdleBrowserReaperConfig
    assert ScrapingIdleBrowserReaperConfig is IdleBrowserReaperConfig
    assert NodriverIdleBrowserReaperConfig is IdleBrowserReaperConfig


@pytest.mark.asyncio
async def test_idle_reaper_excess_worker_reap() -> None:
    """Проверяет закрытие избыточного простаивающего воркера при наличии более одного активного."""
    closed_workers: list[str] = []

    async def close_worker(name: str) -> None:
        closed_workers.append(name)

    now = time.time()
    active_workers = ["worker_1", "worker_2"]
    last_used = {
        "worker_1": now - 150.0,  # простаивает 150с (> 100с idle_timeout)
        "worker_2": now - 20.0,   # использовался недавно
    }

    reaper = IdleBrowserReaper(
        close_worker_fn=close_worker,
        is_worker_busy_fn=lambda name: False,
        get_active_workers_fn=lambda: [w for w in active_workers if w not in closed_workers],
        get_last_used_fn=lambda name: last_used[name],
        idle_timeout_seconds=100.0,
        scale_to_zero_seconds=300.0,
    )

    closed_count = await reaper.reap()

    assert closed_count == 1
    assert closed_workers == ["worker_1"]


@pytest.mark.asyncio
async def test_idle_reaper_scale_to_zero() -> None:
    """Проверяет закрытие последнего оставшегося инстанса по scale_to_zero_seconds."""
    closed_workers: list[str] = []

    async def close_worker(name: str) -> None:
        closed_workers.append(name)

    now = time.time()
    active_workers = ["single_worker"]
    last_used = {
        "single_worker": now - 350.0,  # простаивает 350с (> 300с scale_to_zero)
    }

    reaper = IdleBrowserReaper(
        close_worker_fn=close_worker,
        is_worker_busy_fn=lambda name: False,
        get_active_workers_fn=lambda: [w for w in active_workers if w not in closed_workers],
        get_last_used_fn=lambda name: last_used[name],
        idle_timeout_seconds=100.0,
        scale_to_zero_seconds=300.0,
    )

    closed_count = await reaper.reap()

    assert closed_count == 1
    assert closed_workers == ["single_worker"]


@pytest.mark.asyncio
async def test_idle_reaper_busy_worker_not_reaped() -> None:
    """Проверяет, что занятые обработкой задач воркеры не закрываются даже при превышении таймаута."""
    closed_workers: list[str] = []

    async def close_worker(name: str) -> None:
        closed_workers.append(name)

    now = time.time()
    active_workers = ["busy_worker"]
    last_used = {
        "busy_worker": now - 500.0,
    }

    reaper = IdleBrowserReaper(
        close_worker_fn=close_worker,
        is_worker_busy_fn=lambda name: True,  # воркер занят
        get_active_workers_fn=lambda: [w for w in active_workers if w not in closed_workers],
        get_last_used_fn=lambda name: last_used[name],
        idle_timeout_seconds=50.0,
        scale_to_zero_seconds=100.0,
    )

    closed_count = await reaper.reap()

    assert closed_count == 0
    assert len(closed_workers) == 0


@pytest.mark.asyncio
async def test_idle_reaper_sync_callback_support() -> None:
    """Проверяет работу с синхронной функцией close_worker_fn."""
    closed_workers: list[str] = []

    def sync_close_worker(name: str) -> None:
        closed_workers.append(name)

    now = time.time()
    active_workers = ["w1"]
    last_used = {"w1": now - 200.0}

    reaper = IdleBrowserReaper(
        close_worker_fn=sync_close_worker,
        is_worker_busy_fn=lambda name: False,
        get_active_workers_fn=lambda: [w for w in active_workers if w not in closed_workers],
        get_last_used_fn=lambda name: last_used[name],
        scale_to_zero_seconds=100.0,
    )

    closed = await reaper.reap()
    assert closed == 1
    assert closed_workers == ["w1"]


@pytest.mark.asyncio
async def test_idle_reaper_lifecycle_and_context_manager() -> None:
    """Проверяет start, stop и асинхронный контекстный менеджер."""
    mock_close = AsyncMock()
    reaper = IdleBrowserReaper(
        close_worker_fn=mock_close,
        is_worker_busy_fn=lambda name: False,
        get_active_workers_fn=list,
        get_last_used_fn=lambda name: 0.0,
        check_interval_seconds=0.01,
    )

    assert not reaper.is_running
    reaper.start()
    assert reaper.is_running

    # Повторный start не создает дублирующую таску
    task = reaper._task
    reaper.start()
    assert reaper._task is task

    await reaper.stop()
    assert not reaper.is_running
    assert reaper._task is None

    # Проверка context manager
    async with reaper:
        assert reaper.is_running
    assert not reaper.is_running


def test_idle_reaper_config_presets() -> None:
    """Проверяет пресеты конфигурации IdleReaperConfig."""
    default_cfg = IdleReaperConfig()
    assert default_cfg.idle_timeout_seconds == 120.0
    assert default_cfg.scale_to_zero_seconds == 300.0
    assert default_cfg.check_interval_seconds == 15.0
    assert default_cfg.enabled is True

    aggressive = IdleReaperConfig.preset_aggressive()
    assert aggressive.idle_timeout_seconds == 30.0
    assert aggressive.scale_to_zero_seconds == 60.0
    assert aggressive.check_interval_seconds == 5.0

    relaxed = IdleReaperConfig.preset_relaxed()
    assert relaxed.idle_timeout_seconds == 300.0
    assert relaxed.scale_to_zero_seconds == 900.0
    assert relaxed.check_interval_seconds == 30.0

    keep_warm = IdleReaperConfig.preset_keep_warm()
    assert keep_warm.scale_to_zero_seconds == 0.0


@pytest.mark.asyncio
async def test_idle_reaper_disabled_config() -> None:
    """Проверяет, что при enabled=False воркеры не закрываются."""
    closed_workers: list[str] = []

    async def close_worker(name: str) -> None:
        closed_workers.append(name)

    now = time.time()
    active_workers = ["w1"]
    last_used = {"w1": now - 1000.0}

    cfg = IdleReaperConfig(enabled=False, scale_to_zero_seconds=50.0)
    reaper = IdleBrowserReaper(
        close_worker_fn=close_worker,
        is_worker_busy_fn=lambda name: False,
        get_active_workers_fn=lambda: [w for w in active_workers if w not in closed_workers],
        get_last_used_fn=lambda name: last_used[name],
        config=cfg,
    )

    closed = await reaper.reap()
    assert closed == 0
    assert len(closed_workers) == 0

    # Включаем на лету через configure
    reaper.configure(enabled=True)
    assert reaper.enabled is True
    closed_after = await reaper.reap()
    assert closed_after == 1
    assert closed_workers == ["w1"]


@pytest.mark.asyncio
async def test_idle_reaper_from_config_factory() -> None:
    """Проверяет создание экземпляра через from_config."""
    cfg = IdleReaperConfig(idle_timeout_seconds=42.0, scale_to_zero_seconds=84.0)
    reaper = IdleBrowserReaper.from_config(
        close_worker_fn=AsyncMock(),
        is_worker_busy_fn=lambda name: False,
        get_active_workers_fn=list,
        get_last_used_fn=lambda name: 0.0,
        config=cfg,
    )

    assert reaper.idle_timeout_seconds == 42.0
    assert reaper.scale_to_zero_seconds == 84.0

