import asyncio
import pytest
from unittest.mock import AsyncMock

from chutils.telegram.rate_limit import TelegramRateLimiter, tg_rate_limit
from chutils.exceptions.resilience import RateLimitExceededError


def test_telegram_rate_limiter_basic():
    """Проверяет базовую логику подсчета превышения лимитов."""
    limiter = TelegramRateLimiter(rate=2, per=1.0)

    is_limited, wait_sec = limiter.check_rate_limit("user_1")
    assert is_limited is False

    is_limited, wait_sec = limiter.check_rate_limit("user_1")
    assert is_limited is False

    is_limited, wait_sec = limiter.check_rate_limit("user_1")
    assert is_limited is True
    assert wait_sec > 0.0


def test_tg_rate_limit_sync_raise():
    """Проверяет выброс ошибки при превышении лимита вызовов в синхронном декораторе."""
    @tg_rate_limit(rate=1, per=1.0, raise_on_limit=True)
    def sync_handler(user_id: int):
        return "OK"

    assert sync_handler(user_id=555) == "OK"

    with pytest.raises(RateLimitExceededError):
        sync_handler(user_id=555)


@pytest.mark.asyncio
async def test_tg_rate_limit_async_warning():
    """Проверяет отправку шаблона с временем ожидания при превышении лимита."""
    mock_event = AsyncMock()
    mock_event.from_user.id = 777
    mock_event.answer = AsyncMock()

    @tg_rate_limit(rate=1, per=2.0, warning_text="Wait {wait_sec}s!")
    async def async_handler(event):
        return "SUCCESS"

    res1 = await async_handler(mock_event)
    assert res1 == "SUCCESS"

    res2 = await async_handler(mock_event)
    assert res2 is None
    mock_event.answer.assert_called_once()
    assert "Wait" in mock_event.answer.call_args[0][0]
