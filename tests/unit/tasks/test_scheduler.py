import asyncio
import logging

import pytest

from chutils.lifecycle import LifecycleManager
from chutils.tasks import (
    periodic_task,
    clear_tasks_registry,
    start_scheduler,
    stop_scheduler,
    ErrorStrategy,
)

# Включаем pytest-asyncio
pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def cleanup_registry():
    clear_tasks_registry()
    yield
    # Гарантируем остановку планировщика после каждого теста
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(stop_scheduler())
    except RuntimeError:
        pass
    clear_tasks_registry()


async def test_scheduler_runs_sync_and_async_tasks():
    """Проверяет запуск sync и async задач планировщиком."""
    sync_called = 0
    async_called = 0

    @periodic_task(interval_seconds=1, run_immediately=True)
    def my_sync():
        nonlocal sync_called
        sync_called += 1

    @periodic_task(interval_seconds=1, run_immediately=True)
    async def my_async():
        nonlocal async_called
        async_called += 1

    start_scheduler()

    # Даем немного времени на выполнение
    await asyncio.sleep(0.2)

    assert sync_called >= 1
    assert async_called >= 1

    await stop_scheduler()


async def test_run_immediately_false():
    """Проверяет, что задачи без run_immediately не запускаются сразу."""
    sync_called = 0

    @periodic_task(interval_seconds=2, run_immediately=False)
    def my_sync():
        nonlocal sync_called
        sync_called += 1

    start_scheduler()
    await asyncio.sleep(0.5)

    # Не должна запуститься до 2 секунд
    assert sync_called == 0
    await stop_scheduler()


async def test_overlapping_prevented_by_default():
    """Проверяет, что перекрывающиеся задачи пропускаются по умолчанию (overlap=False)."""
    task_calls = 0
    task_runs = 0

    @periodic_task(interval_seconds=1, run_immediately=True, overlap=False)
    async def slow_task():
        nonlocal task_calls, task_runs
        task_calls += 1
        await asyncio.sleep(1.5)  # Длительность задачи больше интервала
        task_runs += 1

    start_scheduler()

    # Даем времени на 2 тика (через 0с и через 1с)
    # Так как slow_task спит 1.5с, тик на 1с должен быть пропущен.
    await asyncio.sleep(1.2)

    # Первый тик запущен, второй тик пропущен, так как первый еще спит
    assert task_calls == 1
    await stop_scheduler()


async def test_overlapping_allowed_with_flag():
    """Проверяет, что при overlap=True задачи запускаются параллельно."""
    task_calls = 0

    @periodic_task(interval_seconds=1, run_immediately=True, overlap=True)
    async def slow_task():
        nonlocal task_calls
        task_calls += 1
        await asyncio.sleep(1.5)

    start_scheduler()
    await asyncio.sleep(1.2)

    # Должно быть 2 запуска (первый на 0с, второй на 1с), так как они не блокируют друг друга
    assert task_calls == 2
    await stop_scheduler()


async def test_error_strategy_ignore(caplog):
    """Проверяет, что по умолчанию ошибки в задачах игнорируются (только логируются)."""
    calls = 0

    @periodic_task(interval_seconds=1, run_immediately=True, error_strategy=ErrorStrategy.IGNORE)
    def failing_task():
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ValueError("Test error")

    with caplog.at_level(logging.ERROR):
        start_scheduler()
        await asyncio.sleep(1.2)

        # Должно быть 2 запуска (первый упал, второй прошел успешно)
        assert calls == 2
        assert any("Ошибка выполнения задачи" in record.message for record in caplog.records)

        await stop_scheduler()


async def test_error_strategy_stop_task():
    """Проверяет, что при STOP_TASK упавшая задача исключается из планировщика."""
    calls = 0

    @periodic_task(interval_seconds=1, run_immediately=True, error_strategy=ErrorStrategy.STOP_TASK)
    def failing_task():
        nonlocal calls
        calls += 1
        raise ValueError("Critical task error")

    start_scheduler()
    await asyncio.sleep(1.2)

    # Должен быть только 1 запуск, после чего задача прекращает тикать
    assert calls == 1
    await stop_scheduler()


async def test_error_strategy_stop_scheduler():
    """Проверяет, что при STOP_SCHEDULER ошибка в задаче останавливает весь планировщик."""
    import chutils.tasks.core
    chutils.tasks.core._scheduler = None
    calls = 0

    @periodic_task(interval_seconds=1, run_immediately=True, error_strategy=ErrorStrategy.STOP_SCHEDULER)
    def fatal_task():
        nonlocal calls
        calls += 1
        raise ValueError("Fatal scheduler error")

    start_scheduler()

    # Ожидаем в цикле остановки планировщика (максимум 2 секунды)
    for _ in range(20):
        if chutils.tasks.core._scheduler is None:
            break
        await asyncio.sleep(0.1)

    assert chutils.tasks.core._scheduler is None
    assert calls == 1


async def test_graceful_shutdown_integration(mocker):
    """Проверяет интеграцию с chutils.lifecycle для Graceful Shutdown."""
    import chutils.tasks.core
    chutils.tasks.core._scheduler = None

    # Создаем фейковый LifecycleManager
    lm = LifecycleManager()
    mocker.patch("chutils.lifecycle._manager", lm)

    called = 0

    @periodic_task(interval_seconds=2, run_immediately=True)
    def my_task():
        nonlocal called
        called += 1

    start_scheduler()
    await asyncio.sleep(0.2)
    assert called == 1

    # Запускаем очистку в LifecycleManager напрямую асинхронно,
    # чтобы избежать вызова asyncio.run() во время выполняющегося event loop
    await lm._execute_all(lm.get_cleanup_callbacks(), 10.0)

    assert chutils.tasks.core._scheduler is None


async def test_dynamic_interval_callable():
    """Проверяет динамическое вычисление интервала через callable."""
    called = 0
    # Начинаем с интервала в 1 сек, затем меняем
    current_interval = 1

    def get_dynamic_interval():
        return current_interval

    @periodic_task(interval_seconds=get_dynamic_interval, run_immediately=True)
    def my_dynamic_task():
        nonlocal called
        called += 1

    start_scheduler()
    await asyncio.sleep(0.1)
    assert called == 1  # Первый вызов при run_immediately=True

    # Меняем интервал на 2 сек
    current_interval = 2

    # Ждем 1.2 секунды. Поскольку следующий sleep был запланирован с интервалом 1 (предыдущий current_interval),
    # задача сработает через 1 сек.
    await asyncio.sleep(1.2)
    assert called == 2

    # Теперь новый интервал 2 сек, ждем еще 1.2 секунды — сработать не должна, так как ждем 2 сек.
    await asyncio.sleep(1.2)
    assert called == 2

    # Ждем еще 1 секунду (суммарно 2.2с с момента прошлого запуска) — сработает.
    await asyncio.sleep(1.0)
    assert called == 3

    await stop_scheduler()


async def test_dynamic_interval_config(mocker):
    """Проверяет динамическое вычисление интервала через строку конфигурации."""
    called = 0
    # Имитируем get_config_int
    mocker.patch("chutils.config.get_config_int", return_value=1)

    @periodic_task(interval_seconds="scheduler.my_interval", run_immediately=True)
    def my_config_task():
        nonlocal called
        called += 1

    start_scheduler()
    await asyncio.sleep(0.1)
    assert called == 1

    # Ждем один тик в 1 сек
    await asyncio.sleep(1.2)
    assert called == 2

    await stop_scheduler()


async def test_scheduler_task_logging(caplog):
    """Проверяет структурированное логирование запусков периодических задач."""
    @periodic_task(interval_seconds=1, run_immediately=True, name="boosty_sync")
    async def boosty_sync():
        await asyncio.sleep(0.05)

    @periodic_task(interval_seconds=1, run_immediately=True, name="failing_sync", error_strategy=ErrorStrategy.IGNORE)
    def failing_sync():
        raise ValueError("Oops")

    with caplog.at_level(logging.INFO):
        start_scheduler()
        await asyncio.sleep(0.2)
        await stop_scheduler()

    # Проверяем старт задачи
    assert any("Задача 'boosty_sync' запущена." in record.message for record in caplog.records)
    # Проверяем успешное завершение
    assert any("Задача 'boosty_sync' выполнена за" in record.message and "сек." in record.message for record in caplog.records)
    # Проверяем ошибку
    assert any("Ошибка выполнения задачи 'failing_sync': Oops" in record.message for record in caplog.records)

