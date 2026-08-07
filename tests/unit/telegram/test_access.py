import pytest
from unittest.mock import MagicMock, AsyncMock

from chutils.telegram.access import is_admin, admin_only
from chutils.exceptions.telegram import TelegramAccessDeniedError


def test_is_admin_explicit_ids():
    """Проверяет явную проверку по ID пользователя."""
    assert is_admin(user_id=123, admin_ids=[123, 456]) is True
    assert is_admin(user_id=999, admin_ids=[123, 456]) is False


def test_is_admin_explicit_usernames():
    """Проверяет явную проверку по username пользователя (без учета регистра и со значком @)."""
    assert is_admin(username="Alice", admin_usernames=["@alice", "bob"]) is True
    assert is_admin(username="@bob", admin_usernames=["alice", "BOB"]) is True
    assert is_admin(username="eve", admin_usernames=["alice", "bob"]) is False


def test_is_admin_custom_func():
    """Проверяет работу кастомного предиката."""
    func = lambda uid, uname: uid == 777 or uname == "god"
    assert is_admin(user_id=777, is_admin_func=func) is True
    assert is_admin(username="god", is_admin_func=func) is True
    assert is_admin(user_id=1, username="mortal", is_admin_func=func) is False


def test_admin_only_decorator_sync_success():
    """Проверяет синхронный декоратор при успешном доступе."""
    @admin_only(admin_ids=[100])
    def sync_handler(user_id: int):
        return f"OK-{user_id}"

    assert sync_handler(user_id=100) == "OK-100"


def test_admin_only_decorator_sync_denied_raise():
    """Проверяет выбрасывание ошибки TelegramAccessDeniedError в синхронном режиме."""
    @admin_only(admin_ids=[100], raise_on_denied=True)
    def sync_handler(user_id: int):
        return "OK"

    with pytest.raises(TelegramAccessDeniedError):
        sync_handler(user_id=200)


@pytest.mark.asyncio
async def test_admin_only_decorator_async_success():
    """Проверяет асинхронный декоратор при успешном доступе."""
    @admin_only(admin_usernames=["admin"])
    async def async_handler(username: str):
        return f"OK-{username}"

    res = await async_handler(username="admin")
    assert res == "OK-admin"


@pytest.mark.asyncio
async def test_admin_only_decorator_async_denied_answer():
    """Проверяет автоматическую отправку сообщения с отказом в доступе через mock event."""
    mock_event = AsyncMock()
    mock_event.from_user.id = 555
    mock_event.answer = AsyncMock()

    @admin_only(admin_ids=[111], refusal_text="Access Denied!")
    async def async_handler(event):
        return "SECRET_DATA"

    res = await async_handler(mock_event)
    assert res is None
    mock_event.answer.assert_called_once_with("Access Denied!")
