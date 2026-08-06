from __future__ import annotations

from chutils.exceptions.base import ChutilsException


class TelegramError(ChutilsException):
    """Базовое исключение для подсистемы Telegram."""

    pass


class TelegramAccessDeniedError(TelegramError):
    """Выбрасывается при отказе в доступе к командам или действиям Telegram-бота."""

    def __init__(self, message: str = "⛔ Доступ запрещен: требуется статус администратора", user_id: int | None = None) -> None:
        self.user_id = user_id
        super().__init__(message)
