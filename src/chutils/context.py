import contextvars
import logging
import typing

_context: contextvars.ContextVar[typing.Dict[str, typing.Any]] = contextvars.ContextVar("_chutils_context", default={})
"Хранилище контекста: словарь {ключ: значение}"


def get_context() -> typing.Dict[str, typing.Any]:
    """Возвращает копию текущего контекста."""
    return _context.get().copy()


def bind_context(**kwargs) -> contextvars.Token:
    """
    Привязывает значения к текущему контексту.
    Возвращает токен для последующей очистки через unbind_context.
    """
    current = get_context()
    current.update(kwargs)
    return _context.set(current)


def unbind_context(token: contextvars.Token) -> None:
    """Восстанавливает контекст до состояния, предшествующего bind_context."""
    _context.reset(token)


def clear_context() -> None:
    """Полностью очищает текущий контекст."""
    _context.set({})


class ContextFilter(logging.Filter):
    """
    Фильтр, обогащающий LogRecord данными из контекста.
    
    Добавляет:
    - Индивидуальные ключи контекста как атрибуты (для %(key)s).
    - record.context: Строка вида "[key1=val1 key2=val2 ]" или "" если пусто.
    - record.context_dict: Оригинальный словарь контекста (для JSON-логирования).
    """

    def filter(self, record: logging.LogRecord) -> bool:
        ctx = get_context()

        # Добавляем данные трассировки OpenTelemetry, если они доступны
        try:
            from .tracing import get_current_trace_context
            trace_ctx = get_current_trace_context()
            if trace_ctx:
                ctx.update(trace_ctx)
                # Также добавляем как индивидуальные атрибуты для форматтеров
                for key, value in trace_ctx.items():
                    setattr(record, key, value)
        except (ImportError, AttributeError):
            pass

        record.context_dict = ctx

        if not ctx:
            record.context = ""
            return True

        # Формируем строку контекста
        parts = []
        for key, value in ctx.items():
            parts.append(f"{key}={value}")
            # Также добавляем как атрибуты самого рекорда
            setattr(record, key, value)

        record.context = f"[{' '.join(parts)}] "
        return True
