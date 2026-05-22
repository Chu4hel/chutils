"""
Логика маскирования секретов в логах.
"""

import logging
import os
import re
import threading
from typing import Optional, Set

# --- Предустановленные паттерны PII ---

PREDEFINED_PATTERNS = {
    "email": r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+",
    "credit_card": r"\b(?:\d[ -]*?){13,16}\b",
    "phone": r"\b(?:\+?\d{1,3}[- ]?)?\(?\d{3}\)?[- ]?\d{3}[- ]?\d{4}\b",
    "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
}

# --- Глобальное состояние для маскирования секретов ---

_GLOBAL_MASKS: Set[str] = set()
"Глобальный список строк (секретов), которые должны быть заменены на [MASKED] в логах."
_CUSTOM_PATTERNS: Set[str] = set()
"Глобальный список регулярных выражений для маскирования."

_MASK_RE: Optional[re.Pattern] = None
"Скомпилированное регулярное выражение для поиска всех секретов."
_masks_lock = threading.Lock()
"Блокировка для обеспечения потокобезопасности при обновлении масок."


def _update_mask_re():
    """
    Обновляет и компилирует регулярное выражение на основе текущих масок и паттернов.
    """
    global _MASK_RE
    with _masks_lock:
        if not _GLOBAL_MASKS and not _CUSTOM_PATTERNS:
            _MASK_RE = None
            return

        parts = []

        # 1. Добавляем литеральные маски (экранированные)
        if _GLOBAL_MASKS:
            sorted_masks = sorted([m for m in _GLOBAL_MASKS if m], key=len, reverse=True)
            if sorted_masks:
                parts.append("|".join(re.escape(m) for m in sorted_masks))

        # 2. Добавляем кастомные паттерны
        if _CUSTOM_PATTERNS:
            parts.extend(list(_CUSTOM_PATTERNS))

        if not parts:
            _MASK_RE = None
            return

        pattern = "|".join(f"({p})" for p in parts)
        _MASK_RE = re.compile(pattern)


class SecretMaskingFilter(logging.Filter):
    """
    Фильтр для автоматического маскирования секретов в сообщениях логов.

    Ищет в тексте сообщения и в аргументах все зарегистрированные секреты
    и паттерны и заменяет их на '[MASKED]'.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Применяет маскирование к записи лога.

        Args:
            record: Запись лога.

        Returns:
            Всегда True (фильтр не отсеивает записи, а модифицирует их).
        """
        # Если маскирование отключено через окружение, ничего не делаем.
        if os.getenv("CH_DISABLE_LOG_MASKING", "").lower() in ("true", "1", "yes", "y"):
            return True

        if _MASK_RE is None:
            return True

        # Маскируем основное сообщение, если оно является строкой.
        if isinstance(record.msg, str):
            record.msg = _MASK_RE.sub("[MASKED]", record.msg)

        # Маскируем аргументы, если они являются строками.
        if record.args:
            new_args = []
            for arg in record.args:
                if isinstance(arg, str):
                    new_args.append(_MASK_RE.sub("[MASKED]", arg))
                else:
                    new_args.append(arg)
            record.args = tuple(new_args)

        return True
