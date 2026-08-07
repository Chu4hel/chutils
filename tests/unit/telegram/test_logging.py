import pytest
from unittest.mock import AsyncMock, MagicMock

from chutils.telegram.logging import trace_telegram_update


def test_trace_telegram_update_sync_context():
    """Проверяет работу контекстного менеджера трейсинга апдейтов."""
    mock_event = MagicMock()
    mock_event.from_user.id = 12345
    mock_event.chat.id = 67890

    with trace_telegram_update(mock_event):
        pass  # Успешное выполнение


@pytest.mark.asyncio
async def test_trace_telegram_update_async_decorator():
    """Проверяет асинхронный декоратор trace_telegram_update."""
    mock_event = AsyncMock()
    mock_event.from_user.id = 555

    @trace_telegram_update()
    async def sample_handler(event):
        return "SUCCESS"

    res = await sample_handler(mock_event)
    assert res == "SUCCESS"
