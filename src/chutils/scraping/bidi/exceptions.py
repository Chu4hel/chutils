"""Исключения подсистемы WebDriver BiDi."""

from __future__ import annotations


class BiDiError(Exception):
    """Базовое исключение для всех ошибок протокола WebDriver BiDi."""


class BiDiConnectionError(BiDiError):
    """Исключение, возникающее при ошибке сетевого подключения к BiDi WebSocket."""


class BiDiTimeoutError(BiDiError):
    """Исключение при превышении таймаута ожидания ответа от браузера."""


class BiDiCommandError(BiDiError):
    """Исключение при возврате ошибки выполнения команды браузером.

    Attributes:
        error_code: Строковый код ошибки BiDi (например, 'invalid argument').
        message: Сообщение об ошибке от браузера.
        data: Дополнительные данные об ошибке (при наличии).
    """

    def __init__(
        self,
        error_code: str,
        message: str,
        data: dict[str, object] | None = None,
    ) -> None:
        """Инициализирует ошибку команды BiDi.

        Args:
            error_code: Строковый код ошибки BiDi.
            message: Описание ошибки.
            data: Опциональные дополнительные данные.
        """
        super().__init__(f"BiDi error [{error_code}]: {message}")
        self.error_code = error_code
        self.message = message
        self.data = data or {}
