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
    from .core import (
        add_global_handler as add_global_handler,
    )
    from .core import (
        clear_global_handlers as clear_global_handlers,
    )
    from .core import (
        get_global_handlers as get_global_handlers,
    )
    from .core import (
        remove_global_handler as remove_global_handler,
    )
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
    from .intercept import (
        DEFAULT_INTERCEPT_MODULES as DEFAULT_INTERCEPT_MODULES,
    )
    from .intercept import (
        InterceptHandler as InterceptHandler,
    )
    from .intercept import (
        capture_standard_logging as capture_standard_logging,
    )
    from .intercept import (
        intercept_all as intercept_all,
    )
    from .intercept import (
        restore_standard_logging as restore_standard_logging,
    )
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
    "add_global_handler": (".core", "add_global_handler"),
    "remove_global_handler": (".core", "remove_global_handler"),
    "get_global_handlers": (".core", "get_global_handlers"),
    "clear_global_handlers": (".core", "clear_global_handlers"),
    "InterceptHandler": (".intercept", "InterceptHandler"),
    "capture_standard_logging": (".intercept", "capture_standard_logging"),
    "intercept_all": (".intercept", "intercept_all"),
    "restore_standard_logging": (".intercept", "restore_standard_logging"),
    "DEFAULT_INTERCEPT_MODULES": (".intercept", "DEFAULT_INTERCEPT_MODULES"),
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
