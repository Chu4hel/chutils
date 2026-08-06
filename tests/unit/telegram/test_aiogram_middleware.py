import pytest
from unittest.mock import AsyncMock

from chutils.telegram.aiogram import TelegramThrottlingMiddleware, TelegramLoggingMiddleware


@pytest.mark.asyncio
async def test_telegram_throttling_middleware():
    """Проверяет фильтрацию спама через TelegramThrottlingMiddleware."""
    middleware = TelegramThrottlingMiddleware(rate=1, per=1.0, warning_text="Wait!")

    mock_handler = AsyncMock(return_value="HANDLED")

    event = AsyncMock()
    event.from_user.id = 12345
    event.answer = AsyncMock()

    # Запрос 1 - успешен
    res1 = await middleware(mock_handler, event, {})
    assert res1 == "HANDLED"
    assert mock_handler.call_count == 1

    # Запрос 2 - заблокирован
    res2 = await middleware(mock_handler, event, {})
    assert res2 is None
    assert mock_handler.call_count == 1
    event.answer.assert_called_once_with("Wait!")


@pytest.mark.asyncio
async def test_telegram_logging_middleware():
    """Проверяет логирование и трейсинг через TelegramLoggingMiddleware."""
    middleware = TelegramLoggingMiddleware()
    mock_handler = AsyncMock(return_value="LOGGED_OK")

    event = AsyncMock()
    event.from_user.id = 777

    res = await middleware(mock_handler, event, {})
    assert res == "LOGGED_OK"
