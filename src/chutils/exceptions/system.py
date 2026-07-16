import typing as t
from pathlib import Path

from .base import ChutilsException


class CommandError(ChutilsException):
    """Ошибка при выполнении CLI команды."""

    pass


class FileSystemError(ChutilsException):
    """Общая ошибка при работе с файловой системой."""

    pass


class PathTraversalError(FileSystemError):
    """
    Ошибка безопасности: попытка выхода за пределы базовой директории (Path Traversal).
    """

    def __init__(
            self,
            message: str,
            attempted_path: str | Path = "unknown",
            base_path: str | Path = "unknown",
            hint: str | None = "Проверьте правильность пути или права доступа.",
            **context: t.Any,
    ) -> None:
        """Инициализирует исключение попытки выхода за пределы базовой директории.

        Args:
            message: Сообщение об ошибке.
            attempted_path: Недопустимый путь, к которому пытались получить доступ.
            base_path: Базовый разрешенный путь.
            hint: Опциональная подсказка для пользователя.
            **context: Дополнительный контекст ошибки.
        """
        context.update(
            {"attempted_path": str(attempted_path), "base_path": str(base_path)}
        )
        super().__init__(message, hint=hint, **context)
