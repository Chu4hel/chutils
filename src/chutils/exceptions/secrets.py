from .base import ChutilsException


class SecretError(ChutilsException):
    """Общая ошибка менеджера секретов."""


class SecretNotFoundError(SecretError):
    """Ошибка: секрет не найден."""


class SecretProviderError(SecretError):
    """Ошибка конкретного провайдера секретов (например, сбой keyring)."""
