import asyncio
import threading

import pytest

from chutils.events.core import (
    EventBus,
    ErrorStrategy,
    subscribe,
    publish,
    publish_async,
    is_async_callable,
    _run_and_log_errors
)
from chutils.exceptions import EventBusExceptionGroup

# Опционально для Pydantic
try:
    import pydantic

    HAS_PYDANTIC = True


    class DummyModel(pydantic.BaseModel):
        value: str
except ImportError:
    HAS_PYDANTIC = False


def test_is_async_callable():
    async def async_fn():
        pass

    def sync_fn():
        pass

    class SyncCallable:
        def __call__(self):
            pass

    class AsyncCallable:
        async def __call__(self):
            pass

    assert is_async_callable(async_fn) is True
    assert is_async_callable(sync_fn) is False
    assert is_async_callable(SyncCallable()) is False
    assert is_async_callable(AsyncCallable()) is True
    assert is_async_callable("not a callable") is False


def test_subscribe_and_unsubscribe():
    bus = EventBus()

    @bus.subscribe("test_event")
    def handler(x):
        return x * 2

    assert handler in bus._subscribers["test_event"]

    # Отписка существующей функции
    bus.unsubscribe("test_event", handler)
    assert handler not in bus._subscribers["test_event"]

    # Отписка несуществующей функции (не должно вызывать ValueError)
    bus.unsubscribe("test_event", handler)

    # Отписка из несуществующего события
    bus.unsubscribe("non_existent_event", handler)


def test_thread_safety_registry():
    bus = EventBus()
    num_threads = 10
    num_events = 50
    threads = []

    def worker(tid):
        for i in range(num_events):
            event_name = f"event_{i}"

            def h(): pass

            bus.subscribe(event_name)(h)
            bus.unsubscribe(event_name, h)

    for i in range(num_threads):
        t = threading.Thread(target=worker, args=(i,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    # Все подписки должны быть корректно добавлены/удалены
    for event_name, handlers in bus._subscribers.items():
        assert len(handlers) == 0


def test_publish_no_subscribers():
    bus = EventBus()
    # Должно завершиться без ошибок
    bus.publish("some_random_event")


@pytest.mark.asyncio
async def test_publish_async_no_subscribers():
    bus = EventBus()
    # Должно завершиться без ошибок
    await bus.publish_async("some_random_event")


def test_publish_sync_handlers():
    bus = EventBus()
    calls = []

    @bus.subscribe("ping")
    def on_ping(data):
        calls.append(data)

    bus.publish("ping", "pong")
    assert calls == ["pong"]


@pytest.mark.asyncio
async def test_publish_async_handlers():
    bus = EventBus()
    calls = []

    @bus.subscribe("ping")
    async def on_ping(data):
        await asyncio.sleep(0.01)
        calls.append(data)

    @bus.subscribe("ping")
    def on_ping_sync(data):
        calls.append(data + "_sync")

    await bus.publish_async("ping", "pong")
    # Должны выполниться оба обработчика
    assert "pong" in calls
    assert "pong_sync" in calls


def test_publish_async_in_sync_context():
    bus = EventBus()
    calls = []
    event = threading.Event()

    @bus.subscribe("ping")
    async def on_ping(data):
        calls.append(data)
        event.set()

    bus.publish("ping", "pong")

    # Так как асинхронный обработчик запускается в фоне,
    # мы должны подождать установки события.
    assert event.wait(timeout=2.0)
    assert calls == ["pong"]


def test_error_strategy_ignore(caplog):
    bus = EventBus(error_strategy=ErrorStrategy.IGNORE)
    calls = []

    @bus.subscribe("error_event")
    def bad_handler():
        raise ValueError("Oops")

    @bus.subscribe("error_event")
    def good_handler():
        calls.append(1)

    caplog.clear()
    bus.publish("error_event")

    assert calls == [1]
    assert any("Ошибка в синхронном обработчике события" in record.message for record in caplog.records)


def test_error_strategy_fail_fast():
    bus = EventBus(error_strategy=ErrorStrategy.FAIL_FAST)

    @bus.subscribe("error_event")
    def bad_handler():
        raise ValueError("Oops")

    with pytest.raises(ValueError, match="Oops"):
        bus.publish("error_event")


def test_error_strategy_collect():
    bus = EventBus(error_strategy=ErrorStrategy.COLLECT)

    @bus.subscribe("error_event")
    def bad_handler1():
        raise ValueError("Oops 1")

    @bus.subscribe("error_event")
    def bad_handler2():
        raise KeyError("Oops 2")

    with pytest.raises(EventBusExceptionGroup) as excinfo:
        bus.publish("error_event")

    assert len(excinfo.value.exceptions) == 2
    assert any(isinstance(e, ValueError) for e in excinfo.value.exceptions)
    assert any(isinstance(e, KeyError) for e in excinfo.value.exceptions)
    assert "Возникшие ошибки" in str(excinfo.value)


@pytest.mark.asyncio
async def test_error_strategy_collect_async():
    bus = EventBus(error_strategy=ErrorStrategy.COLLECT)

    @bus.subscribe("error_event")
    async def bad_handler1():
        raise ValueError("Oops 1")

    @bus.subscribe("error_event")
    def bad_handler2():
        raise KeyError("Oops 2")

    with pytest.raises(EventBusExceptionGroup) as excinfo:
        await bus.publish_async("error_event")

    assert len(excinfo.value.exceptions) == 2


@pytest.mark.asyncio
async def test_error_strategy_fail_fast_async():
    bus = EventBus(error_strategy=ErrorStrategy.FAIL_FAST)

    @bus.subscribe("error_event")
    async def bad_handler1():
        raise ValueError("Oops 1")

    @bus.subscribe("error_event")
    def bad_handler2():
        # Этот тоже выполнится, но gather выбросит первую ошибку
        pass

    with pytest.raises(ValueError, match="Oops 1"):
        await bus.publish_async("error_event")


@pytest.mark.asyncio
async def test_error_strategy_ignore_async(caplog):
    bus = EventBus(error_strategy=ErrorStrategy.IGNORE)
    calls = []

    @bus.subscribe("error_event")
    async def bad_handler():
        raise ValueError("Oops")

    @bus.subscribe("error_event")
    def good_handler():
        calls.append(1)

    caplog.clear()
    await bus.publish_async("error_event")

    assert calls == [1]
    assert any("Ошибка в обработчике события" in record.message for record in caplog.records)


@pytest.mark.skipif(not HAS_PYDANTIC, reason="Pydantic is not installed")
def test_pydantic_payload():
    bus = EventBus()
    calls = []

    @bus.subscribe("event_model")
    def handle_model(event_obj):
        calls.append(event_obj.value)

    model = DummyModel(value="hello pydantic")
    bus.publish("event_model", model)
    assert calls == ["hello pydantic"]


@pytest.mark.asyncio
async def test_global_bus_interface():
    calls = []

    @subscribe("global_event")
    def handle_global(data):
        calls.append(data)

    @subscribe("global_event")
    async def handle_global_async(data):
        calls.append(data + "_async")

    publish("global_event", "ping")
    await publish_async("global_event", "pong")

    # Синхронная публикация в глобальной шине может запустить асинхронный обработчик в фоне.
    # Поэтому подождем немного, пока обработаются все вызовы.
    await asyncio.sleep(0.05)

    assert "ping" in calls
    assert "pong" in calls
    assert "pong_async" in calls


@pytest.mark.asyncio
async def test_run_and_log_errors_helper(caplog):
    async def bad_coro():
        raise ValueError("coro error")

    caplog.clear()
    await _run_and_log_errors(bad_coro(), "test_event")

    assert any(
        "Ошибка в асинхронном фоновом обработчике события test_event" in record.message for record in caplog.records)
