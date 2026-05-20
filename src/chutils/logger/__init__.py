"""
Модуль для настройки логирования.

Этот пакет разделен на модули для соблюдения SRP:
- core: Основной класс логгера и setup_logger.
- masking: Фильтрация секретов.
- formatters: Форматирование (Text, JSON).
- handlers: Обработчики файлов (ротация, сжатие).
"""

from .core import (
    setup_logger,
    ChutilsLogger,
    LogLevel,
    DEVDEBUG_LEVEL_NUM,
    MEDIUMDEBUG_LEVEL_NUM
)
from .formatters import ChutilsJsonFormatter, JSON_LOGGER_AVAILABLE
from .handlers import (
    SafeTimedRotatingFileHandler,
    CompressingRotatingFileHandler,
    CompressingTimedRotatingFileHandler
)
from .masking import SecretMaskingFilter

__all__ = [
    'setup_logger',
    'ChutilsLogger',
    'LogLevel',
    'SecretMaskingFilter',
    'ChutilsJsonFormatter',
    'JSON_LOGGER_AVAILABLE',
    'SafeTimedRotatingFileHandler',
    'CompressingRotatingFileHandler',
    'CompressingTimedRotatingFileHandler',
    'DEVDEBUG_LEVEL_NUM',
    'MEDIUMDEBUG_LEVEL_NUM'
]
