from .base import ChutilsException


class DependencyError(ChutilsException):
    """Общая ошибка внедрения зависимостей."""


class DependencyNotFoundError(DependencyError):
    """Ошибка: запрашиваемая зависимость не зарегистрирована в контейнере."""


class DependencyResolutionError(DependencyError):
    """Ошибка при разрешении графа зависимостей (например, некорректная сигнатура, циклические зависимости)."""
