import typing as t

from pydantic import BaseModel

T = t.TypeVar("T", bound="BaseEnvManifest")


class BaseEnvManifest(BaseModel):
    """Базовый манифест переменных окружения на базе Pydantic."""

    @classmethod
    def load(cls: type[T]) -> T: ...


def has_pydantic() -> bool: ...


def has_rich() -> bool: ...


def has_watchdog() -> bool: ...


def is_rich_enabled() -> bool: ...


def is_otel_enabled() -> bool: ...


RICH_AVAILABLE: bool
PYDANTIC_AVAILABLE: bool
WATCHDOG_AVAILABLE: bool
JSON_LOGGER_AVAILABLE: bool
OTEL_AVAILABLE: bool
