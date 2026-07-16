import typing as t

from .base import ChutilsException, _BaseExceptionGroup


class EventBusError(ChutilsException):
    """Общая ошибка шины событий."""

    pass


class EventBusExceptionGroup(_BaseExceptionGroup, EventBusError):
    """
    Группа ошибок, возникших при параллельном или последовательном выполнении
    обработчиков событий шины.
    """

    def __init__(
            self, message: str, exceptions: list[Exception], **context: t.Any
    ) -> None:
        """Инициализирует группу исключений шины событий.

        Args:
            message: Сообщение об ошибке.
            exceptions: Список перехваченных исключений от обработчиков.
            **context: Дополнительный контекст ошибки.
        """
        _BaseExceptionGroup.__init__(self, message, exceptions)
        EventBusError.__init__(self, message, **context)

    def __str__(self) -> str:
        base_str = EventBusError.__str__(self)
        errors_str = "\n".join(f"  - {type(e).__name__}: {e}" for e in self.exceptions)
        return f"{base_str}\nВозникшие ошибки:\n{errors_str}"
