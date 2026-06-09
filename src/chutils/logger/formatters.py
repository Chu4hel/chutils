"""
Форматтеры для логов.
"""

from __future__ import annotations

import logging
from typing import Any, TYPE_CHECKING

from chutils.env import JSON_LOGGER_AVAILABLE

if JSON_LOGGER_AVAILABLE:
    try:
        from pythonjsonlogger import jsonlogger
    except ImportError:
        try:
            # Fallback for older versions or slightly different package structures
            from pythonjsonlogger import json as jsonlogger  # type: ignore[no-redef]
        except ImportError:
            JSON_LOGGER_AVAILABLE = False
            jsonlogger = Any
else:
    jsonlogger = Any

if TYPE_CHECKING:
    class _BaseFormatter(logging.Formatter):
        def add_fields(self, log_record: dict[str, Any], record: logging.LogRecord,
                       message_dict: dict[str, Any]) -> None: ...
else:
    if JSON_LOGGER_AVAILABLE and jsonlogger is not Any:
        _BaseFormatter = jsonlogger.JsonFormatter
    else:
        _BaseFormatter = logging.Formatter


class ChutilsJsonFormatter(_BaseFormatter):
    """
    Кастомный JSON-форматтер, который группирует контекстные данные
    во вложенный объект 'context', а данные трассировки выносит на верхний уровень.
    """

    def add_fields(self, log_record: dict[str, Any], record: logging.LogRecord, message_dict: dict[str, Any]) -> None:
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
