"""VKMA (VK Mini Apps) exceptions."""

from chutils.exceptions.base import ChutilsException


class VKMAValidationError(ChutilsException):
    """Выбрасывается при ошибке валидации параметров запуска (launchParams) или подписи VKMA."""

    def __init__(self, message: str, hint: str | None = None, **context: str | int | float | bool | None) -> None:
        super().__init__(message, hint=hint, **context)


__all__ = ["VKMAValidationError"]
