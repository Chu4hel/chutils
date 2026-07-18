"""Утилиты для вычисления хэша записей журнала аудита."""
from __future__ import annotations

import hashlib
import json


def compute_record_hash(record: dict[str, object]) -> str:
    """Вычисляет SHA-256 хэш записи аудита.

    Хэш вычисляется от канонического JSON-представления словаря
    без поля 'hash'. Порядок ключей фиксируется через sort_keys=True.

    Args:
        record: Словарь полей записи аудита (без поля 'hash').

    Returns:
        Hex-строка SHA-256 длиной 64 символа.
    """
    data = {k: v for k, v in record.items() if k != "hash"}
    canonical = json.dumps(data, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()
