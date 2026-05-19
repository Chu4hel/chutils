"""
Логика маскирования секретов в логах.
"""

import logging
import os
import re
import threading
from typing import Optional, Set

# --- Глобальное состояние для маскирования секретов ---

_GLOBAL_MASKS: Set[str] = set()
"Глобальный список строк (секретов), которые должны быть заменены на *** в логах."
_MASK_RE: Optional[re.Pattern] = None
"Скомпилированное регулярное выражение для поиска всех секретов."
_masks_lock = threading.Lock()
"Блокировка для обеспечения потокобезопасности при обновлении масок."


def _update_mask_re():
    """
    Обновляет и компилирует регулярное выражение на основе текущих масок.
    """
    global _MASK_RE
    with _masks_lock:
        if not _GLOBAL_MASKS:
            _MASK_RE = None
            return

        # Сортируем маски по длине (от длинных к коротким), чтобы сначала находить подстроки большей длины.
        # Экранируем спецсимволы регулярных выражений.
        sorted_masks = sorted([m for m in _GLOBAL_MASKS if m], key=len, reverse=True)
        if not sorted_masks:
            _MASK_RE = None
            return

        pattern = "|".join(re.escape(m) for m in sorted_masks)
        _MASK_RE = re.compile(pattern)


class SecretMaskingFilter(logging.Filter):
    """
    Фильтр для автоматического маскирования секретов в сообщениях логов.

    Ищет в тексте сообщения и в аргументах все зарегистрированные секреты
    и заменяет их на '***'.
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
            record.msg = _MASK_RE.sub("***", record.msg)

        # Маскируем аргументы, если они являются строками.
        if record.args:
            new_args = []
            for arg in record.args:
                if isinstance(arg, str):
                    new_args.append(_MASK_RE.sub("***", arg))
                else:
                    new_args.append(arg)
            record.args = tuple(new_args)

        return True
