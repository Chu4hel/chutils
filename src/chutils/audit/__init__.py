"""
chutils.audit — Неизменяемый журнал событий аудита.

Предоставляет:
- AuditEvent: Pydantic-схема записи аудита с криптографической цепочкой.
- BaseAuditBackend, FileBackend, SqliteBackend, PostgresBackend: бэкенды хранения.
- audit_event: декоратор для автоматической регистрации событий.
- audit_context: контекстный менеджер для блока операций.

Использование:
    from chutils.audit import FileBackend, audit_event

    backend = FileBackend("audit.jsonl")

    @audit_event(action="user.login", actor="system")
    def login(user_id: str) -> None:
        ...
"""
from chutils.audit.backends.base import BaseAuditBackend
from chutils.audit.backends.file import FileBackend
from chutils.audit.backends.sqlite import SqliteBackend
from chutils.audit.schema import AuditEvent

# Опциональные — доступны после Фазы 2
try:
    from chutils.audit.backends.postgres import PostgresBackend
except ImportError:
    PostgresBackend = None  # type: ignore[assignment,misc]

try:
    from chutils.audit.api import audit_event, audit_context
except ImportError:
    audit_event = None  # type: ignore[assignment]
    audit_context = None  # type: ignore[assignment]

__all__ = [
    "AuditEvent",
    "BaseAuditBackend",
    "FileBackend",
    "SqliteBackend",
    "PostgresBackend",
    "audit_event",
    "audit_context",
]
