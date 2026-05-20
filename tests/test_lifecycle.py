import pytest
import asyncio
import signal
import time
from unittest.mock import MagicMock
from chutils.lifecycle import register_cleanup, setup_graceful_shutdown, _manager

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

def test_setup_graceful_shutdown(mocker):
    """Тест настройки обработчиков сигналов."""
    mock_signal = mocker.patch("signal.signal")
    
    setup_graceful_shutdown()
    
    # Проверяем, что signal.signal был вызван для SIGINT, SIGTERM, SIGHUP
    # Мы не проверяем точное количество вызовов, так как оно может зависеть от платформы, 
    # но основные сигналы должны быть покрыты.
    mock_signal.assert_any_call(signal.SIGINT, _manager._handle_signal)
    mock_signal.assert_any_call(signal.SIGTERM, _manager._handle_signal)
    assert _manager._setup_done is True

def test_execution_logic(mocker):
    """Тест логики выполнения коллбэков при получении сигнала."""
    mock_sync = MagicMock()
    mock_async = mocker.AsyncMock()
    
    register_cleanup(mock_sync)
    register_cleanup(mock_async)
    
    # Мокаем sys.exit, чтобы тест не завершился
    mocker.patch("sys.exit")
    
    # Эмулируем получение сигнала
    _manager._handle_signal(signal.SIGINT, None)
    
    mock_sync.assert_called_once()
    mock_async.assert_called_once()

def test_execution_error_handling(mocker):
    """Тест обработки ошибок: выполнение должно продолжаться при сбое одного коллбэка."""
    mock_fail = MagicMock(side_effect=Exception("Boom"))
    mock_success = MagicMock()
    
    register_cleanup(mock_success)
    register_cleanup(mock_fail)
    
    mocker.patch("sys.exit")
    
    # ACT
    _manager._handle_signal(signal.SIGINT, None)
    
    # ASSERT
    mock_fail.assert_called_once()
    mock_success.assert_called_once() # Должен быть вызван несмотря на ошибку в mock_fail

def test_timeout_mechanism(mocker):
    """Тест механизма таймаута."""
    async def slow_func():
        await asyncio.sleep(0.5)
        
    mock_after = MagicMock()
    
    register_cleanup(mock_after)
    register_cleanup(slow_func)
    
    # Мокаем конфиг: таймаут 0.1 сек
    mocker.patch("chutils.lifecycle.get_config_int", return_value=0.1)
    mocker.patch("sys.exit")
    
    # ACT
    _manager._handle_signal(signal.SIGINT, None)
    
    # ASSERT
    mock_after.assert_not_called() # Не должен быть вызван из-за таймаута
