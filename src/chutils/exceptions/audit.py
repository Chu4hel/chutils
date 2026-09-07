"""Исключения модуля chutils.audit."""

from .base import ChutilsException


class AuditError(ChutilsException):
    """Базовый класс ошибок модуля audit."""


class AuditIntegrityError(AuditError):
    """Ошибка целостности журнала аудита.

    Выбрасывается при обнаружении нарушения криптографической цепочки хэшей.
    """
