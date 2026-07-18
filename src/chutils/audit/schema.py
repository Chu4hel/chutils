"""
Схема события аудита AuditEvent.

Описывает единую запись журнала аудита. Каждая запись включает
криптографический хэш (SHA-256), вычисленный от всех её полей
плюс хэш предыдущей записи, что образует неизменяемую цепочку.

Pydantic используется для валидации, но модуль импортируется безопасно:
при отсутствии Pydantic сам по себе не ломает chutils.
"""
from __future__ import annotations

import os
import socket
import threading
import uuid
from datetime import datetime


def _build_audit_event_class() -> type:
    """Строит класс AuditEvent через Pydantic или dataclass-fallback.

    Returns:
        Класс AuditEvent.

    Raises:
        ImportError: Если Pydantic не установлен (только при реальном использовании).
    """
    try:
        from pydantic import BaseModel, Field, model_validator
    except ImportError:
        raise ImportError(
            "Pydantic требуется для chutils.audit. "
            "Установите: pip install chutils[pydantic]"
        )

    from chutils.audit._hash import compute_record_hash

    def _collect_env() -> dict[str, object]:
        return {
            "hostname": socket.gethostname(),
            "pid": os.getpid(),
            "thread_name": threading.current_thread().name,
        }

    class AuditEvent(BaseModel):
        """Pydantic-модель единой записи журнала аудита.

        Attributes:
            id: UUID записи (генерируется автоматически).
            timestamp: Время события в UTC (генерируется автоматически).
            actor: Субъект действия (user_123, system и т.д.).
            action: Название операции (user.login, db.write и т.д.).
            target: Объект операции (опционально).
            status: Результат операции — 'success' или 'failed'.
            details: Произвольные детали события.
            env: Автоматически собранный контекст окружения (hostname, pid, thread_name).
            prev_hash: SHA-256 хэш предыдущей записи ('' для первой).
            hash: SHA-256 хэш текущей записи (вычисляется автоматически).
        """

        model_config = {"frozen": True}

        id: str = Field(default_factory=lambda: str(uuid.uuid4()))
        timestamp: datetime = Field(
            default_factory=lambda: __import__("chutils.time", fromlist=["utc_now"]).utc_now()
        )
        actor: str
        action: str
        target: str | None = None
        status: str = "success"
        details: dict[str, object] = Field(default_factory=dict)
        env: dict[str, object] = Field(default_factory=_collect_env)
        prev_hash: str = ""
        hash: str = ""

        @model_validator(mode="after")
        def _compute_hash_field(self) -> "AuditEvent":
            """Вычисляет и устанавливает hash после валидации всех полей."""
            if not self.hash:
                # mode="json" гарантирует datetime -> ISO-строка,
                # чтобы хэш совпадал при верификации из JSON/JSONL
                computed = compute_record_hash(self.model_dump(mode="json"))
                object.__setattr__(self, "hash", computed)
            return self

        def to_jsonl(self) -> str:
            """Сериализует запись в строку JSON Lines.

            Returns:
                Однострочный JSON без завершающего символа переноса строки.
            """
            return self.model_dump_json()

        @classmethod
        def from_jsonl(cls, line: str) -> "AuditEvent":
            """Десериализует запись из строки JSON Lines.

            Args:
                line: Строка JSON.

            Returns:
                Восстановленный экземпляр AuditEvent.
            """
            return cls.model_validate_json(line)

    return AuditEvent


# Экспортируем класс
try:
    AuditEvent = _build_audit_event_class()
except ImportError:
    AuditEvent = None  # type: ignore[assignment,misc]

__all__ = ["AuditEvent"]
