"""
Логика маскирования секретов в логах.
"""

from __future__ import annotations

import logging  # chutils: ignore[ChutilsIntegrationRule]
import os
import re
import threading
from typing import Any

# --- Предустановленные паттерны PII ---

PREDEFINED_PATTERNS = {
    "email": r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+",
    "credit_card": r"\b(?:\d[ -]*?){13,16}\b",
    "phone": r"\b(?:\+?\d{1,3}[- ]?)?\(?\d{3}\)?[- ]?\d{3}[- ]?\d{4}\b",
    "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
}

# --- Глобальное состояние для маскирования секретов ---

_GLOBAL_MASKS: set[str] = set()
"Глобальный список строк (секретов), которые должны быть заменены на [MASKED] в логах."
_CUSTOM_PATTERNS: set[str] = set()
"Глобальный список регулярных выражений для маскирования."

_MASK_RE: re.Pattern[str] | None = None
"Скомпилированное регулярное выражение для поиска всех секретов."
_masks_lock = threading.Lock()
"Блокировка для обеспечения потокобезопасности при обновлении масок."


def _update_mask_re() -> None:
    """
    Обновляет и компилирует регулярное выражение на основе текущих масок и паттернов.
    """
    global _MASK_RE
    with _masks_lock:
        if not _GLOBAL_MASKS and not _CUSTOM_PATTERNS:
            _MASK_RE = None
            return

        parts: list[str] = []

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


def register_secret_mask(secret: str) -> None:
    """Регистрирует подстроку (секрет) для глобального маскирования в логах.

    Args:
        secret: Значение секрета (пароль, токен и т.д.).
    """
    if secret:
        _GLOBAL_MASKS.add(secret)
        _update_mask_re()


def register_pattern_mask(pattern: str) -> None:
    """Регистрирует регулярное выражение для глобального маскирования в логах.

    Args:
        pattern: Строка регулярного выражения.
    """
    if pattern:
        _CUSTOM_PATTERNS.add(pattern)
        _update_mask_re()


def clear_masks() -> None:
    """Сбрасывает все зарегистрированные маски и регулярные выражения."""
    _GLOBAL_MASKS.clear()
    _CUSTOM_PATTERNS.clear()
    _update_mask_re()


class SecretMaskingFilter(logging.Filter):
    """
    Фильтр для автоматического маскирования секретов в сообщениях логов.

    Ищет в тексте сообщения и в аргументах все зарегистрированные секреты
    и паттерны и заменяет их на '[MASKED]'.
    """

    def __init__(
        self,
        name: str = "",
        secrets: list[str] | set[str] | None = None,
        patterns: list[str] | set[str] | None = None,
    ) -> None:
        """Инициализирует фильтр маскирования секретов.

        Args:
            name: Имя фильтра (стандартный аргумент logging.Filter).
            secrets: Опциональный список локальных/глобальных секретов для маскирования.
            patterns: Опциональный список регулярных выражений для маскирования.
        """
        super().__init__(name)
        if secrets:
            for s in secrets:
                if s:
                    _GLOBAL_MASKS.add(s)
        if patterns:
            for p in patterns:
                if p:
                    _CUSTOM_PATTERNS.add(p)
        if secrets or patterns:
            _update_mask_re()


    def filter(self, record: logging.LogRecord) -> bool:
        """
        Применяет маскирование к записи лога.

        Args:
            record: Запись лога.

        Returns:
            Всегда True (фильтр не отсеивает записи, а модифицирует их).
        """
        # Если маскирование отключено через окружение, ничего не делаем.
        if os.getenv("CH_DISABLE_LOG_MASKING", "").lower() in ("true", "1", "yes", "y"):  # chutils: ignore[ChutilsIntegrationRule]
            return True

        if _MASK_RE is None:
            return True

        # Маскируем основное сообщение, если оно является строкой.
        if isinstance(record.msg, str):
            record.msg = _MASK_RE.sub("[MASKED]", record.msg)

        # Маскируем аргументы, если они являются строками.
        if record.args:
            new_args: list[Any] = []
            # Если record.args это словарь, мы не можем его просто итерировать как список
            # Но стандартный logging.Filter предполагает что args это кортеж или словарь.
            # В случае словаря sub() не сработает напрямую.
            if isinstance(record.args, dict):
                new_dict_args: dict[Any, Any] = {}
                for k, v in record.args.items():
                    if isinstance(v, str):
                        new_dict_args[k] = _MASK_RE.sub("[MASKED]", v)
                    else:
                        new_dict_args[k] = v
                record.args = new_dict_args
            else:
                for arg in record.args:
                    if isinstance(arg, str):
                        new_args.append(_MASK_RE.sub("[MASKED]", arg))
                    else:
                        new_args.append(arg)
                record.args = tuple(new_args)

        return True
