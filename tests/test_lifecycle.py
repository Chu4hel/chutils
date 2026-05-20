import pytest

from chutils.lifecycle import register_cleanup, _manager


@pytest.fixture(autouse=True)
def cleanup_registry():
    """Очищает реестр перед каждым тестом."""
    _manager._clear_registry()
    yield


def test_register_sync_cleanup():
    """Тест регистрации синхронной функции."""

    def sync_func():
        pass

    returned = register_cleanup(sync_func)
    assert returned == sync_func
    assert sync_func in _manager._cleanup_callbacks


@pytest.mark.asyncio
async def test_register_async_cleanup():
    """Тест регистрации асинхронной функции."""

    async def async_func():
        pass

    returned = register_cleanup(async_func)
    assert returned == async_func
    assert async_func in _manager._cleanup_callbacks


def test_lifo_order():
    """Тест порядка LIFO (Last-In-First-Out)."""

    def func1(): pass

    def func2(): pass

    async def func3(): pass

    register_cleanup(func1)
    register_cleanup(func2)
    register_cleanup(func3)

    callbacks = _manager.get_cleanup_callbacks()
    assert callbacks == [func3, func2, func1]


def test_decorator_usage():
    """Тест использования как декоратора."""

    @register_cleanup
    def decorated():
        pass

    assert decorated in _manager._cleanup_callbacks


def test_prevent_duplicate_registration():
    """Тест предотвращения дублирования функций в реестре."""

    def func(): pass

    register_cleanup(func)
    register_cleanup(func)

    assert len(_manager._cleanup_callbacks) == 1
