import typing as t
from pathlib import Path


class ChutilsException(Exception):
    """
    Базовый класс для всех исключений библиотеки chutils.
    
    Поддерживает структурированный контекст ошибки через именованные аргументы
    и опциональную подсказку (hint) для пользователя.
    """

    def __init__(self, message: str, hint: t.Optional[str] = None, **context: t.Any) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint
        self.context = context

    def __str__(self) -> str:
        parts = [self.message]

        if self.context:
            context_str = ", ".join(f"{k}={v!r}" for k, v in self.context.items())
            parts.append(f"[Контекст: {context_str}]")

        if self.hint:
            parts.append(f"\nСОВЕТ: {self.hint}")

        return " ".join(parts)


# --- Config Exceptions ---

class ConfigError(ChutilsException):
    """Общая ошибка конфигурации."""
    pass


class ConfigLoadError(ConfigError):
    """Ошибка при загрузке файла конфигурации (отсутствие файла, права доступа)."""
    pass


class ConfigParseError(ConfigError):
    """Ошибка при парсинге содержимого конфигурации (невалидный YAML/JSON/INI)."""
    pass


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
            attempted_path: t.Union[str, Path] = "unknown",
            base_path: t.Union[str, Path] = "unknown",
            hint: t.Optional[str] = "Проверьте правильность пути или права доступа.",
            **context: t.Any
    ) -> None:
        context.update({
            "attempted_path": str(attempted_path),
            "base_path": str(base_path)
        })
        super().__init__(message, hint=hint, **context)


# --- Cache Exceptions ---

class CacheError(ChutilsException):
    """Общая ошибка кэширования."""
    pass


# --- Event Bus Exceptions ---

class EventBusError(ChutilsException):
    """Общая ошибка шины событий."""
    pass


class EventBusExceptionGroup(EventBusError):
    """
    Группа ошибок, возникших при параллельном или последовательном выполнении
    обработчиков событий шины.
    """

    def __init__(self, message: str, exceptions: list[Exception], **context: t.Any) -> None:
        super().__init__(message, **context)
        self.exceptions = exceptions

    def __str__(self) -> str:
        base_str = super().__str__()
        errors_str = "\n".join(f"  - {type(e).__name__}: {e}" for e in self.exceptions)
        return f"{base_str}\nВозникшие ошибки:\n{errors_str}"


# --- Rate Limiting Exceptions ---

class RateLimitExceededError(ChutilsException):
    """Ошибка: превышен лимит частоты вызовов (Rate Limit Exceeded)."""
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
