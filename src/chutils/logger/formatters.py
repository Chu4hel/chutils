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
        во вложенный объект 'context'.
        """

        def add_fields(self, log_record, record, message_dict):
            super().add_fields(log_record, record, message_dict)
            if hasattr(record, 'context_dict') and record.context_dict:
                log_record['context'] = record.context_dict

except ImportError:
    JSON_LOGGER_AVAILABLE = False
