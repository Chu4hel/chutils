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


try:
    from aiogram import BaseMiddleware

    _HAS_AIOGRAM_MIDDLEWARE = True
except ImportError:  # pragma: no cover
    BaseMiddleware = object
    _HAS_AIOGRAM_MIDDLEWARE = False


class TelegramThrottlingMiddleware(BaseMiddleware):  # type: ignore[misc]
    """Middleware отслеживания и предотвращения спама (Throttling) для aiogram 3.x."""

    def __init__(
        self,
        rate: int = 1,
        per: float = 1.0,
        scope: str = "user_id",
        warning_text: str | None = "⏱ Пожалуйста, подождите {wait_sec} сек. перед повторной отправкой.",
        silent: bool = False,
    ) -> None:
        if _HAS_AIOGRAM_MIDDLEWARE:
            super().__init__()
        from chutils.telegram.rate_limit import TelegramRateLimiter

        self.limiter = TelegramRateLimiter(rate=rate, per=per)
        self.scope = scope
        self.warning_text = warning_text
        self.silent = silent

    async def __call__(
        self,
        handler: Callable[[Any, dict[str, Any]], Any],
        event: Any,
        data: dict[str, Any],
    ) -> Any:
        """Обрабатывает входящее событие в цепочке Middleware."""
        uid, _ = _extract_user_info((event,), data)
        key = f"user_{uid}" if uid is not None else "unknown"

        is_limited, wait_sec = self.limiter.check_rate_limit(key)
        if is_limited:
            if self.silent:
                return None
            if self.warning_text:
                msg = self.warning_text.format(wait_sec=wait_sec)
                if hasattr(event, "answer") and callable(event.answer):
                    try:
                        await event.answer(msg)
                    except Exception:
                        pass
                elif hasattr(event, "reply") and callable(event.reply):
                    try:
                        await event.reply(msg)
                    except Exception:
                        pass
            return None

        return await handler(event, data)
