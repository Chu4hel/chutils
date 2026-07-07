"""Модуль для обработки текстовых данных.

Предоставляет функции для естественной сортировки строк и нечеткого сравнения
текстов на схожесть с использованием библиотеки RapidFuzz.
"""

import re

try:
    import rapidfuzz

    _HAS_RAPIDFUZZ = True
except ImportError:  # pragma: no cover
    _HAS_RAPIDFUZZ = False

__all__ = ["natsort_key", "is_significant_difference"]


def natsort_key(s: str) -> list[int | str]:
    """Возвращает ключ для естественной (natural) сортировки строки.

    Разбивает строку на сегменты из текста и чисел, преобразуя числовые сегменты в целые числа.
    Используется в качестве аргумента `key` в функциях `sorted()`, `list.sort()` и др.

    Args:
        s: Строка для анализа.

    Returns:
        Список, состоящий из текстовых сегментов (str) и чисел (int).
    """
    return [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', s)]


def is_significant_difference(text1: str, text2: str, threshold: float = 0.9) -> bool:
    """Проверяет, является ли разница между двумя текстами значительной.

    Использует библиотеку RapidFuzz для вычисления схожести строк. Если схожесть
    строго меньше заданного порога (threshold), разница считается значительной.

    Args:
        text1: Первый сравниваемый текст.
        text2: Второй сравниваемый текст.
        threshold: Порог схожести от 0.0 до 1.0 (по умолчанию 0.9, что соответствует 90%).

    Returns:
        True, если разница значительна (схожесть < threshold), иначе False.

    Raises:
        RuntimeError: Если библиотека rapidfuzz не установлена.
    """
    if not _HAS_RAPIDFUZZ:
        raise RuntimeError(
            "Для использования нечеткого сравнения текстов необходимо установить chutils с поддержкой [text]:\n"
            "pip install chutils[text]"
        )
    similarity = float(rapidfuzz.fuzz.ratio(text1, text2))
    return similarity < (threshold * 100.0)
