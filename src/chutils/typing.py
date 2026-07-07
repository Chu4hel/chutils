"""
Модуль для хранения общих протоколов и сложных типов проекта.
Используется для обеспечения строгой типизации (Zero-Any Strategy).
"""

from typing import TypeVar, Protocol, runtime_checkable, Any

# Поддержка ParamSpec и TypeAlias для Python < 3.10
from typing import ParamSpec, TypeAlias

# Общие переменные типов
T = TypeVar("T")
R = TypeVar("R")
P = ParamSpec("P")

# Тип для JSON-подобных структур
JSONDict: TypeAlias = dict[str, Any]
JSONValue: TypeAlias = str | int | float | bool | None | list[Any] | dict[str, Any]


@runtime_checkable
class ConfigProviderProtocol(Protocol):
    """Протокол для провайдеров конфигурации."""

    def load(self, path: str) -> JSONDict:
        ...

    def save(self, path: str, section: str, key: str, value: Any) -> bool:
        ...


@runtime_checkable
class SecretProviderProtocol(Protocol):
    """Протокол для провайдеров секретов."""

    def get_secret(self, name: str) -> str | None:
        ...

    def set_secret(self, name: str, value: str) -> bool:
        ...

    def delete_secret(self, name: str) -> bool:
        ...


@runtime_checkable
class LoggerProtocol(Protocol):
    """Минимальный интерфейс логгера chutils."""

    def debug(self, msg: str, *args: Any, **kwargs: Any) -> None: ...

    def info(self, msg: str, *args: Any, **kwargs: Any) -> None: ...

    def warning(self, msg: str, *args: Any, **kwargs: Any) -> None: ...

    def error(self, msg: str, *args: Any, **kwargs: Any) -> None: ...

    def critical(self, msg: str, *args: Any, **kwargs: Any) -> None: ...

    def devdebug(self, msg: str, *args: Any, **kwargs: Any) -> None: ...

    def mediumdebug(self, msg: str, *args: Any, **kwargs: Any) -> None: ...
