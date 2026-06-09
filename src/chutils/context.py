from __future__ import annotations

import contextvars
import logging
import sys
from typing import Any

# Предотвращаем раздвоение контекста при двойном импорте (например, chutils.context и src.chutils.context)
_chutils_context_var = getattr(sys, "_chutils_context_var", None)
if _chutils_context_var is None:
    _chutils_context_var = contextvars.ContextVar("_chutils_context", default={})
    setattr(sys, "_chutils_context_var", _chutils_context_var)

_context: contextvars.ContextVar[dict[str, Any]] = _chutils_context_var


def get_context() -> dict[str, Any]:
    """Возвращает копию текущего контекста."""
    return _context.get().copy()


def bind_context(**kwargs: Any) -> contextvars.Token[dict[str, Any]]:
    """
    Привязывает значения к текущему контексту.
    Возвращает токен для последующей очистки через unbind_context.
    """
    current = get_context()
    current.update(kwargs)
    return _context.set(current)


def unbind_context(token: contextvars.Token[dict[str, Any]]) -> None:
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
        except Exception:
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
