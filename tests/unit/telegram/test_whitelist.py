import pytest
from pathlib import Path

from chutils.telegram.whitelist import AccessListManager, allowed_only
from chutils.exceptions.telegram import TelegramAccessDeniedError


def test_access_list_manager_basic():
    """Проверяет разрешения по разрешенным и заблокированным спискам."""
    mgr = AccessListManager(allowed_ids=[100], blocked_usernames=["bad_user"])

    assert mgr.is_user_allowed(user_id=100) is True
    assert mgr.is_user_allowed(username="bad_user") is False
    assert mgr.is_user_allowed(user_id=200) is False


def test_access_list_manager_dynamic_and_persistence(tmp_path: Path):
    """Проверяет динамическое изменение списков и сохранение в файл."""
    file_path = tmp_path / "access.json"
    mgr = AccessListManager(storage_path=file_path)

    mgr.allow_user("cool_dev")
    mgr.block_user(999)

    assert mgr.is_user_allowed(username="cool_dev") is True
    assert mgr.is_user_allowed(user_id=999) is False

    # Загружаем заново
    mgr2 = AccessListManager(storage_path=file_path)
    assert mgr2.is_user_allowed(username="cool_dev") is True
    assert mgr2.is_user_allowed(user_id=999) is False


def test_allowed_only_decorator():
    """Проверяет работы декоратора @allowed_only."""
    @allowed_only(allowed_ids=[777], raise_on_denied=True)
    def protected_handler(user_id: int):
        return "GRANTED"

    assert protected_handler(user_id=777) == "GRANTED"

    with pytest.raises(TelegramAccessDeniedError):
        protected_handler(user_id=888)
