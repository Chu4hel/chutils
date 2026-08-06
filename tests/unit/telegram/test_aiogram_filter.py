import pytest
from unittest.mock import AsyncMock

from chutils.telegram.aiogram import AdminFilter, _HAS_AIOGRAM


@pytest.mark.asyncio
async def test_admin_filter_matches():
    """Проверяет соответствие пользователя правилу фильтра AdminFilter."""
    filter_obj = AdminFilter(admin_ids=[100, 200])

    event_admin = AsyncMock()
    event_admin.from_user.id = 100

    event_user = AsyncMock()
    event_user.from_user.id = 999

    assert await filter_obj(event_admin) is True
    assert await filter_obj(event_user) is False


@pytest.mark.asyncio
async def test_admin_filter_usernames():
    """Проверяет проверку по юзернейму в AdminFilter."""
    filter_obj = AdminFilter(admin_usernames=["admin_user"])

    event = AsyncMock()
    event.from_user.id = 555
    event.from_user.username = "Admin_User"

    assert await filter_obj(event) is True
