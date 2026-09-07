from chutils.exceptions import ChutilsException


class CaptchaError(ChutilsException):
    """Базовая ошибка при решении капчи."""


class CaptchaTimeoutError(CaptchaError):
    """Ошибка: превышено время ожидания решения капчи."""


class CaptchaBalanceError(CaptchaError):
    """Ошибка: недостаточный баланс на аккаунте сервиса капчи."""


class CaptchaServiceError(CaptchaError):
    """Ошибка: сервис решения капчи вернул ошибку API (например, неверный ключ, плохие параметры)."""
