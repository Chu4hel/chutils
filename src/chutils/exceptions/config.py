import typing as t

from .base import ChutilsException, _BaseExceptionGroup


class ConfigError(ChutilsException):
    """Общая ошибка конфигурации."""

    pass


class ConfigLoadError(ConfigError):
    """Ошибка при загрузке файла конфигурации (отсутствие файла, права доступа)."""

    pass


class ConfigParseError(ConfigError):
    """Ошибка при парсинге содержимого конфигурации (невалидный YAML/JSON/INI)."""

    pass


class ConfigKeyNotFoundError(ConfigError):
    """Ошибка: ключ или секция конфигурации не найдены."""

    pass


class ConfigValidationGroupError(_BaseExceptionGroup, ConfigError):
    """Группа ошибок валидации ключей конфигурации (отсутствие обязательных ключей)."""

    def __new__(cls, message: str, exceptions: list[Exception], **context: t.Any) -> "ConfigValidationGroupError":
        # BaseExceptionGroup неизменяем, поэтому конструируем его через __new__
        self = _BaseExceptionGroup.__new__(cls, message, exceptions)
        return self

    def __init__(self, message: str, exceptions: list[Exception], **context: t.Any) -> None:
        """Инициализирует группу ошибок валидации конфигурации.

        Args:
            message: Сообщение об ошибке.
            exceptions: Список исключений ConfigKeyNotFoundError.
            **context: Дополнительный контекст ошибки.
        """
        # _BaseExceptionGroup уже инициализирован через __new__
        ConfigError.__init__(self, message, **context)

    def __str__(self) -> str:
        base_str = ConfigError.__str__(self)
        errors_str = "\n".join(f"  - {e}" for e in self.exceptions)
        return f"{base_str}\nНедостающие ключи:\n{errors_str}"
