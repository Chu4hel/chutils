import sys
import typing as t

if t.TYPE_CHECKING:
    class _BaseExceptionGroup(BaseException):
        exceptions: list[Exception]
else:
    if sys.version_info >= (3, 11):
        _BaseExceptionGroup = ExceptionGroup  # noqa: F821
    else:
        from exceptiongroup import ExceptionGroup as _BaseExceptionGroup  # noqa: F401


class ChutilsException(Exception):
    """
    Базовый класс для всех исключений библиотеки chutils.

    Поддерживает структурированный контекст ошибки через именованные аргументы
    и опциональную подсказку (hint) для пользователя.
    """

    def __init__(self, message: str, hint: str | None = None, **context: t.Any) -> None:
        """Инициализирует базовое исключение ChutilsException.

        Args:
            message: Сообщение об ошибке.
            hint: Опциональная подсказка по устранению ошибки.
            **context: Дополнительный контекст ошибки.
        """
        super().__init__(message)
        self._message = message
        self.hint = hint
        self.context = context

    @property
    def message(self) -> str:
        """Сообщение об ошибке.

        Returns:
            Текст сообщения об ошибке.
        """
        return self._message

    def __str__(self) -> str:
        parts = [self.message]

        if self.context:
            context_str = ", ".join(f"{k}={v!r}" for k, v in self.context.items())
            parts.append(f"[Контекст: {context_str}]")

        if self.hint:
            parts.append(f"\nСОВЕТ: {self.hint}")

        return " ".join(parts)


class OptionalDependencyError(ChutilsException):
    """Ошибка: отсутствует опциональная зависимость (например, watchdog)."""

    pass


class ChutilsTimeoutError(ChutilsException):
    """Ошибка: превышено время ожидания выполнения операции."""

    pass
