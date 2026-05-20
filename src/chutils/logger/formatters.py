"""
Форматтеры для логов.
"""

try:
    try:
        from pythonjsonlogger import json as json_mod

        jsonlogger = json_mod
    except ImportError:
        from pythonjsonlogger import jsonlogger
    JSON_LOGGER_AVAILABLE = True


    class ChutilsJsonFormatter(jsonlogger.JsonFormatter):
        """
        Кастомный JSON-форматтер, который группирует контекстные данные
        во вложенный объект 'context', а данные трассировки выносит на верхний уровень.
        """

        def add_fields(self, log_record, record, message_dict):
            super().add_fields(log_record, record, message_dict)

            # Добавляем данные контекста
            if hasattr(record, 'context_dict') and record.context_dict:
                # Создаем копию, чтобы не менять оригинал при удалении ключей трассировки
                ctx = record.context_dict.copy()

                # Выносим trace_id и span_id на верхний уровень, если они есть
                if 'trace_id' in ctx:
                    log_record['trace_id'] = ctx.pop('trace_id')
                if 'span_id' in ctx:
                    log_record['span_id'] = ctx.pop('span_id')

                if ctx:
                    log_record['context'] = ctx

            # Фолбэк, если ключи есть в record, но не в context_dict
            if 'trace_id' not in log_record and hasattr(record, 'trace_id'):
                log_record['trace_id'] = record.trace_id
            if 'span_id' not in log_record and hasattr(record, 'span_id'):
                log_record['span_id'] = record.span_id

except ImportError:
    JSON_LOGGER_AVAILABLE = False
