import asyncio
from unittest.mock import MagicMock, patch, AsyncMock

import pytest
from chutils.decorators import retry


def test_retry_sync_success_first_try():
    """Проверка успешного выполнения с первой попытки."""
    mock_func = MagicMock(return_value="success")

    decorated = retry(retries=3)(mock_func)
    result = decorated("test")

    assert result == "success"
    assert mock_func.call_count == 1
    mock_func.assert_called_once_with("test")


def test_retry_sync_success_after_retries():
    """Проверка успешного выполнения после нескольких неудачных попыток."""
    mock_func = MagicMock(side_effect=[ValueError("fail"), ValueError("fail"), "success"])

    with patch("time.sleep") as mock_sleep:
        decorated = retry(retries=3, delay=0.1, backoff=2.0)(mock_func)
        result = decorated()

        assert result == "success"
        assert mock_func.call_count == 3
        assert mock_sleep.call_count == 2
        # Проверка задержек: 0.1, 0.2
        mock_sleep.assert_any_call(0.1)
        mock_sleep.assert_any_call(0.2)


def test_retry_sync_exhausted_retries():
    """Проверка выбрасывания исключения после исчерпания всех попыток."""
    mock_func = MagicMock(side_effect=ValueError("persistent fail"))

    with patch("time.sleep"):
        decorated = retry(retries=2)(mock_func)
        with pytest.raises(ValueError, match="persistent fail"):
            decorated()

        assert mock_func.call_count == 3  # 1 попытка + 2 повтора


def test_retry_sync_specific_exceptions():
    """Проверка фильтрации исключений."""
    mock_func = MagicMock(side_effect=[TypeError("wrong type"), "success"])

    # Декоратор настроен только на ValueError
    decorated = retry(retries=3, exceptions=(ValueError,))(mock_func)

    with pytest.raises(TypeError, match="wrong type"):
        decorated()

    assert mock_func.call_count == 1


def test_retry_sync_logging(caplog):
    """Проверка логирования неудачных попыток."""
    mock_func = MagicMock(side_effect=[ValueError("error 1"), "success"])

    # Устанавливаем уровень логирования для захвата и разрешаем распространение (propagate)
    # так как в chutils.logger по умолчанию propagate=False
    import chutils.decorators
    logger = chutils.decorators._get_logger()
    logger.propagate = True

    with caplog.at_level("WARNING", logger=logger.name):
        with patch("time.sleep"):
            decorated = retry(retries=3)(mock_func)
            decorated()

            assert "Попытка 1/3 завершилась ошибкой: error 1" in caplog.text

    # Возвращаем в исходное состояние (опционально, но хорошо для изоляции)
    logger.propagate = False


@patch("time.sleep")
def test_retry_sync_jitter(mock_sleep):
    """Проверка работы jitter."""
    mock_func = MagicMock(side_effect=[ValueError("fail"), "success"])

    # Фиксируем случайное число для предсказуемости
    with patch("random.uniform", return_value=0.05):
        decorated = retry(retries=3, delay=1.0, jitter=True)(mock_func)
        decorated()

        # Ожидаемая задержка: 1.0 + 0.05 = 1.05
        mock_sleep.assert_called_once_with(1.05)


def test_retry_async_success_first_try():
    """Проверка асинхронного выполнения с первой попытки."""
    mock_func = AsyncMock(return_value="success")

    decorated = retry(retries=3)(mock_func)
    result = asyncio.run(decorated("test"))

    assert result == "success"
    assert mock_func.call_count == 1


def test_retry_async_success_after_retries():
    """Проверка асинхронного выполнения после неудач."""
    mock_func = AsyncMock(side_effect=[ValueError("fail"), "success"])

    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        decorated = retry(retries=3, delay=0.5)(mock_func)
        result = asyncio.run(decorated())

        assert result == "success"
        assert mock_func.call_count == 2
        mock_sleep.assert_called_once_with(0.5)


def test_retry_async_exhausted_retries():
    """Проверка асинхронного выброса исключения."""
    mock_func = AsyncMock(side_effect=ValueError("async fail"))

    with patch("asyncio.sleep", new_callable=AsyncMock):
        decorated = retry(retries=1)(mock_func)
        with pytest.raises(ValueError, match="async fail"):
            asyncio.run(decorated())

        assert mock_func.call_count == 2
