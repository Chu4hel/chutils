from .base import ChutilsException


class SecretError(ChutilsException):
    """Общая ошибка менеджера секретов."""

    pass


class SecretNotFoundError(SecretError):
    """Ошибка: секрет не найден."""

    pass


class SecretProviderError(SecretError):
    """Ошибка конкретного провайдера секретов (например, сбой keyring)."""

    pass
