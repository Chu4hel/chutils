"""
Модуль для настройки логирования.

Этот пакет разделен на модули для соблюдения SRP:
- core: Основной класс логгера и setup_logger.
- masking: Фильтрация секретов.
- formatters: Форматирование (Text, JSON).
- handlers: Обработчики файлов (ротация, сжатие).
"""

import importlib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .core import DEVDEBUG_LEVEL_NUM as DEVDEBUG_LEVEL_NUM
    from .core import MEDIUMDEBUG_LEVEL_NUM as MEDIUMDEBUG_LEVEL_NUM
    from .core import ChutilsLogger as ChutilsLogger
    from .core import LogLevel as LogLevel
    from .core import setup_logger as setup_logger
    from .core import setup_logger_from_config as setup_logger_from_config
    from .filters import (
        FlappingFilter as FlappingFilter,
    )
    from .formatters import JSON_LOGGER_AVAILABLE as JSON_LOGGER_AVAILABLE
    from .formatters import ChutilsJsonFormatter as ChutilsJsonFormatter
    from .handlers import (
        CompressingRotatingFileHandler as CompressingRotatingFileHandler,
    )
    from .handlers import (
        CompressingTimedRotatingFileHandler as CompressingTimedRotatingFileHandler,
    )
    from .handlers import SafeTimedRotatingFileHandler as SafeTimedRotatingFileHandler
    from .masking import (
        SecretMaskingFilter as SecretMaskingFilter,
    )
    from .masking import (
        clear_masks as clear_masks,
    )
    from .masking import (
        register_pattern_mask as register_pattern_mask,
    )
    from .masking import (
        register_secret_mask as register_secret_mask,
    )

_LAZY_MAPPING = {
    "setup_logger": (".core", "setup_logger"),
    "setup_logger_from_config": (".core", "setup_logger_from_config"),
    "ChutilsLogger": (".core", "ChutilsLogger"),
    "LogLevel": (".core", "LogLevel"),
    "DEVDEBUG_LEVEL_NUM": (".core", "DEVDEBUG_LEVEL_NUM"),
    "MEDIUMDEBUG_LEVEL_NUM": (".core", "MEDIUMDEBUG_LEVEL_NUM"),
    "FlappingFilter": (".filters", "FlappingFilter"),
    "ChutilsJsonFormatter": (".formatters", "ChutilsJsonFormatter"),
    "JSON_LOGGER_AVAILABLE": (".formatters", "JSON_LOGGER_AVAILABLE"),
    "SafeTimedRotatingFileHandler": (".handlers", "SafeTimedRotatingFileHandler"),
    "CompressingRotatingFileHandler": (".handlers", "CompressingRotatingFileHandler"),
    "CompressingTimedRotatingFileHandler": (
        ".handlers",
        "CompressingTimedRotatingFileHandler",
    ),
    "SecretMaskingFilter": (".masking", "SecretMaskingFilter"),
    "register_secret_mask": (".masking", "register_secret_mask"),
    "register_pattern_mask": (".masking", "register_pattern_mask"),
    "clear_masks": (".masking", "clear_masks"),
}


def __getattr__(name: str) -> Any:
    if name in _LAZY_MAPPING:
        mod_path, attr_name = _LAZY_MAPPING[name]
        module = importlib.import_module(mod_path, __name__)
        return getattr(module, attr_name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(
        list(_LAZY_MAPPING.keys())
        + [
            "__all__",
            "__doc__",
            "__file__",
            "__path__",
            "__name__",
            "__package__",
            "__spec__",
        ]
    )


__all__ = list(_LAZY_MAPPING.keys())
