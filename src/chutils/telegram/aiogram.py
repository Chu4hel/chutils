from __future__ import annotations

from collections.abc import Callable
from typing import Any

from chutils.exceptions.base import OptionalDependencyError
from chutils.telegram.access import is_admin, _extract_user_info

try:
    from aiogram.filters import BaseFilter

    _HAS_AIOGRAM = True
except ImportError:  # pragma: no cover
    BaseFilter = object
    _HAS_AIOGRAM = False


class AdminFilter(BaseFilter):  # type: ignore[misc]
    """Фильтр проверки прав администратора для aiogram 3.x.

    Пример использования:
        @router.message(AdminFilter(admin_ids=[12345678]))
        async def admin_cmd(message: Message):
            await message.answer("Привет, админ!")
    """

    def __init__(
        self,
        admin_ids: list[int] | None = None,
        admin_usernames: list[str] | None = None,
        is_admin_func: Callable[[int | None, str | None], bool] | None = None,
    ) -> None:
        if _HAS_AIOGRAM:
            super().__init__()
        self.admin_ids = admin_ids
        self.admin_usernames = admin_usernames
        self.is_admin_func = is_admin_func

    async def __call__(self, event: Any, **kwargs: Any) -> bool:
        """Проверяет, отправлено ли событие (Message/CallbackQuery) администратором.

        Args:
            event: Объект Telegram Update / Message / CallbackQuery из aiogram.
            **kwargs: Дополнительные контекстные данные.

        Returns:
            True, если пользователь является администратором.
        """
        uid, uname = _extract_user_info((event,), kwargs)
        return is_admin(
            user_id=uid,
            username=uname,
            admin_ids=self.admin_ids,
            admin_usernames=self.admin_usernames,
            is_admin_func=self.is_admin_func,
        )
