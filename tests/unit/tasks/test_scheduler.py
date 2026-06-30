import pytest

from chutils.tasks import periodic_task, get_registered_tasks, clear_tasks_registry, ErrorStrategy


@pytest.fixture(autouse=True)
def cleanup_registry():
    clear_tasks_registry()
    yield
    clear_tasks_registry()


def test_periodic_task_registration():
    """Проверяет корректность регистрации задач декоратором."""

    @periodic_task(interval_seconds=10, run_immediately=True, overlap=True, error_strategy=ErrorStrategy.STOP_TASK)
    def my_sync_task():
        return 42

    @periodic_task(interval_seconds=5, name="custom_async")
    async def my_async_task():
        pass

    tasks = get_registered_tasks()
    assert len(tasks) == 2

    # Проверка первой задачи
    task1 = tasks[0]
    assert task1.name == "my_sync_task"
    assert task1.interval_seconds == 10
    assert task1.run_immediately is True
    assert task1.overlap is True
    assert task1.error_strategy == ErrorStrategy.STOP_TASK
    assert task1.is_async is False

    # Проверка второй задачи
    task2 = tasks[1]
    assert task2.name == "custom_async"
    assert task2.interval_seconds == 5
    assert task2.run_immediately is False
    assert task2.overlap is False
    assert task2.error_strategy == ErrorStrategy.IGNORE
    assert task2.is_async is True


def test_invalid_interval():
    """Проверяет ошибку при некорректном интервале."""
    with pytest.raises(ValueError, match="Interval must be a positive integer"):
        @periodic_task(interval_seconds=0)
        def invalid_task():
            pass

    with pytest.raises(ValueError, match="Interval must be a positive integer"):
        @periodic_task(interval_seconds=-5)
        def negative_task():
            pass
