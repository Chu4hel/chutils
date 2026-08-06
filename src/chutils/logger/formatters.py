"""
Форматтеры для логов.
"""

from __future__ import annotations

import logging  # chutils: ignore[ChutilsIntegrationRule]
from typing import Any, TYPE_CHECKING

from chutils.env import JSON_LOGGER_AVAILABLE

_jsonlogger: Any = None

if JSON_LOGGER_AVAILABLE:
    try:
        # Prefer new import path to avoid DeprecationWarning in version 3.2.0+
        from pythonjsonlogger import json as _json_module

        _jsonlogger = _json_module
    except ImportError:
        try:
            # Fallback for older versions
            from pythonjsonlogger import jsonlogger as _json_module_old

            _jsonlogger = _json_module_old
        except ImportError:
            JSON_LOGGER_AVAILABLE = False
            _jsonlogger = None
else:
    _jsonlogger = None

if TYPE_CHECKING:
    class _BaseFormatter(logging.Formatter):
        def add_fields(self, log_record: dict[str, Any], record: logging.LogRecord,
                       message_dict: dict[str, Any]) -> None:
            """Добавляет поля в словарь записи лога."""
            ...
else:
    if JSON_LOGGER_AVAILABLE and _jsonlogger is not None:
        _BaseFormatter = _jsonlogger.JsonFormatter
    else:
        _BaseFormatter = logging.Formatter


class ChutilsJsonFormatter(_BaseFormatter):
    """
    Кастомный JSON-форматтер, который группирует контекстные данные
    во вложенный объект 'context', а данные трассировки выносит на верхний уровень.
    """

    def add_fields(self, log_record: dict[str, Any], record: logging.LogRecord, message_dict: dict[str, Any]) -> None:
        """Добавляет кастомные поля в запись JSON-лога.

        Args:
            log_record: Итоговый словарь записи лога для сериализации.
            record: Оригинальный объект LogRecord.
            message_dict: Дополнительные параметры сообщения.
        """
        if not JSON_LOGGER_AVAILABLE:
            return

        super().add_fields(log_record, record, message_dict)

        # Добавляем данные контекста
        if hasattr(record, 'context_dict'):
            context_dict = getattr(record, 'context_dict')
            if isinstance(context_dict, dict) and context_dict:
                # Создаем копию, чтобы не менять оригинал при удалении ключей трассировки
                ctx = context_dict.copy()

                # Выносим trace_id и span_id на верхний уровень, если они есть
                if 'trace_id' in ctx:
                    log_record['trace_id'] = ctx.pop('trace_id')
                if 'span_id' in ctx:
                    log_record['span_id'] = ctx.pop('span_id')

                if ctx:
                    log_record['context'] = ctx

        # Фолбэк, если ключи есть в record, но не в context_dict
        if 'trace_id' not in log_record and hasattr(record, 'trace_id'):
            log_record['trace_id'] = getattr(record, 'trace_id')
        if 'span_id' not in log_record and hasattr(record, 'span_id'):
            log_record['span_id'] = getattr(record, 'span_id')


__all__ = ["ChutilsJsonFormatter", "JSON_LOGGER_AVAILABLE"]
