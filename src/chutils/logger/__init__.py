"""
Модуль для настройки логирования.

Этот пакет разделен на модули для соблюдения SRP:
- core: Основной класс логгера и setup_logger.
- masking: Фильтрация секретов.
- formatters: Форматирование (Text, JSON).
- handlers: Обработчики файлов (ротация, сжатие).
"""

import importlib
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .core import (
        setup_logger as setup_logger,
        ChutilsLogger as ChutilsLogger,
        LogLevel as LogLevel,
        DEVDEBUG_LEVEL_NUM as DEVDEBUG_LEVEL_NUM,
        MEDIUMDEBUG_LEVEL_NUM as MEDIUMDEBUG_LEVEL_NUM
    )
    from .formatters import ChutilsJsonFormatter as ChutilsJsonFormatter, JSON_LOGGER_AVAILABLE as JSON_LOGGER_AVAILABLE
    from .handlers import (
        SafeTimedRotatingFileHandler as SafeTimedRotatingFileHandler,
        CompressingRotatingFileHandler as CompressingRotatingFileHandler,
        CompressingTimedRotatingFileHandler as CompressingTimedRotatingFileHandler
    )
    from .masking import SecretMaskingFilter as SecretMaskingFilter

_LAZY_MAPPING = {
    'setup_logger': ('.core', 'setup_logger'),
    'ChutilsLogger': ('.core', 'ChutilsLogger'),
    'LogLevel': ('.core', 'LogLevel'),
    'DEVDEBUG_LEVEL_NUM': ('.core', 'DEVDEBUG_LEVEL_NUM'),
    'MEDIUMDEBUG_LEVEL_NUM': ('.core', 'MEDIUMDEBUG_LEVEL_NUM'),
    'ChutilsJsonFormatter': ('.formatters', 'ChutilsJsonFormatter'),
    'JSON_LOGGER_AVAILABLE': ('.formatters', 'JSON_LOGGER_AVAILABLE'),
    'SafeTimedRotatingFileHandler': ('.handlers', 'SafeTimedRotatingFileHandler'),
    'CompressingRotatingFileHandler': ('.handlers', 'CompressingRotatingFileHandler'),
    'CompressingTimedRotatingFileHandler': ('.handlers', 'CompressingTimedRotatingFileHandler'),
    'SecretMaskingFilter': ('.masking', 'SecretMaskingFilter'),
}

def __getattr__(name: str) -> Any:
    if name in _LAZY_MAPPING:
        mod_path, attr_name = _LAZY_MAPPING[name]
        module = importlib.import_module(mod_path, __name__)
        return getattr(module, attr_name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

def __dir__() -> list[str]:
    return sorted(list(_LAZY_MAPPING.keys()) + [
        '__all__', '__doc__', '__file__', '__path__',
        '__name__', '__package__', '__spec__'
    ])

__all__ = list(_LAZY_MAPPING.keys())
