import sys
import typing as t
from pathlib import Path

if t.TYPE_CHECKING:
    class _BaseExceptionGroup(BaseException):
        exceptions: list[Exception]
else:
    if sys.version_info >= (3, 11):
        _BaseExceptionGroup = ExceptionGroup  # noqa: F821
    else:
        from exceptiongroup import ExceptionGroup as _BaseExceptionGroup


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


# --- Config Exceptions ---


class ChutilsConfigurationError(ChutilsException):
    """Ошибка конфигурации компонентов chutils."""

    pass


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

    def __new__(cls, message: str, exceptions: list[Exception], **context: t.Any):
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


# --- Secret Manager Exceptions ---


class SecretError(ChutilsException):
    """Общая ошибка менеджера секретов."""

    pass


class SecretNotFoundError(SecretError):
    """Ошибка: секрет не найден."""

    pass


class SecretProviderError(SecretError):
    """Ошибка конкретного провайдера секретов (например, сбой keyring)."""

    pass


# --- Logger Exceptions ---


class LoggerConfigurationError(ChutilsException):
    """Ошибка конфигурации логгера."""

    pass


# --- Other Exceptions ---


class WatcherInitializationError(ChutilsException):
    """Ошибка инициализации наблюдателя (watcher) за файлами."""

    pass


class OptionalDependencyError(ChutilsException):
    """Ошибка: отсутствует опциональная зависимость (например, watchdog)."""

    pass


class ChutilsTimeoutError(ChutilsException):
    """Ошибка: превышено время ожидания выполнения операции."""

    pass


# --- Command Exceptions ---


class CommandError(ChutilsException):
    """Ошибка при выполнении CLI команды."""

    pass


# --- FS Exceptions ---


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


# --- Cache Exceptions ---


class CacheError(ChutilsException):
    """Общая ошибка кэширования."""

    pass


# --- Event Bus Exceptions ---


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


# --- Rate Limiting Exceptions ---


class RateLimitExceededError(ChutilsException):
    """Ошибка: превышен лимит частоты вызовов (Rate Limit Exceeded)."""

    pass


# --- Circuit Breaker Exceptions ---


class CircuitBreakerOpenError(ChutilsException):
    """Ошибка: цепь предохранителя открыта (запросы заблокированы)."""

    pass


# --- Dependency Injection Exceptions ---


class DependencyError(ChutilsException):
    """Общая ошибка внедрения зависимостей."""

    pass


class DependencyNotFoundError(DependencyError):
    """Ошибка: запрашиваемая зависимость не зарегистрирована в контейнере."""

    pass


class DependencyResolutionError(DependencyError):
    """Ошибка при разрешении графа зависимостей (например, некорректная сигнатура, циклические зависимости)."""

    pass
