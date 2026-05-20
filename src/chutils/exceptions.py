import typing as t


class ChutilsException(Exception):
    """
    Базовый класс для всех исключений библиотеки chutils.
    
    Поддерживает структурированный контекст ошибки через именованные аргументы.
    """

    def __init__(self, message: str, **context: t.Any) -> None:
        super().__init__(message)
        self.message = message
        self.context = context

    def __str__(self) -> str:
        if not self.context:
            return self.message

        context_str = ", ".join(f"{k}={v!r}" for k, v in self.context.items())
        return f"{self.message} [Контекст: {context_str}]"


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
