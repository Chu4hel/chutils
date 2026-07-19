"""
PostgresBackend — хранение журнала аудита в PostgreSQL.

Использует переданное соединение (psycopg2/psycopg/asyncpg или любой
DBAPI-совместимый объект). Импорт бэкенда безопасен при отсутствии драйверов.
"""
from __future__ import annotations

import json
import threading
from typing import TYPE_CHECKING

from chutils.audit._hash import compute_record_hash
from chutils.audit.backends.base import BaseAuditBackend

if TYPE_CHECKING:
    from typing import Protocol, Any


    class _DBAPICursor(Protocol):
        def execute(self, query: str, params: tuple[Any, ...] | dict[str, Any] | None = None) -> Any: ...

        def fetchone(self) -> Any: ...

        def fetchall(self) -> list[tuple[Any, ...]]: ...

        def __enter__(self) -> _DBAPICursor: ...

        def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> object: ...


    class _DBAPIConnection(Protocol):
        def cursor(self) -> _DBAPICursor: ...

        def commit(self) -> None: ...

_CREATE_TABLE = """
                CREATE TABLE IF NOT EXISTS audit_log
                (
                    id
                    TEXT
                    NOT
                    NULL,
                    timestamp
                    TEXT
                    NOT
                    NULL,
                    actor
                    TEXT
                    NOT
                    NULL,
                    action
                    TEXT
                    NOT
                    NULL,
                    target
                    TEXT,
                    status
                    TEXT
                    NOT
                    NULL,
                    details
                    TEXT
                    NOT
                    NULL,
                    env
                    TEXT
                    NOT
                    NULL,
                    prev_hash
                    TEXT
                    NOT
                    NULL,
                    hash
                    TEXT
                    NOT
                    NULL
                ) \
                """

_INSERT = """
          INSERT INTO audit_log
          (id, timestamp, actor, action, target, status, details, env, prev_hash, hash)
          VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) \
          """

_SELECT_LAST_HASH = "SELECT hash FROM audit_log ORDER BY id DESC LIMIT 1"

_SELECT_ALL = (
    "SELECT id, actor, action, target, status, details, env, "
    "timestamp, prev_hash, hash FROM audit_log ORDER BY id"
)


class PostgresBackend(BaseAuditBackend):
    """Бэкенд хранения событий аудита в PostgreSQL.

    Принимает DBAPI2-совместимый объект соединения (psycopg2, psycopg и т.д.).
    Не импортирует драйвер самостоятельно — управление соединением
    остаётся на стороне приложения.

    Args:
        connection: Открытое DBAPI2-соединение с PostgreSQL.
    """
    _conn: _DBAPIConnection

    def __init__(self, connection: _DBAPIConnection) -> None:
        """Инициализирует PostgresBackend и создаёт таблицу audit_log.

        Args:
            connection: Открытое DBAPI2-соединение с PostgreSQL.
        """
        self._conn = connection
        self._lock = threading.Lock()
        self._ensure_table()

    def _ensure_table(self) -> None:
        with self._conn.cursor() as cur:
            cur.execute(_CREATE_TABLE)

    def _get_last_hash(self) -> str:
        with self._conn.cursor() as cur:
            cur.execute(_SELECT_LAST_HASH)
            row = cur.fetchone()
        return row[0] if row else ""

    def log(
            self,
            action: str,
            actor: str,
            *,
            target: str | None = None,
            status: str = "success",
            details: dict[str, object] | None = None,
    ) -> str:
        """Добавляет событие в таблицу audit_log PostgreSQL.

        Args:
            action: Название операции.
            actor: Субъект действия.
            target: Объект операции (опционально).
            status: Результат — 'success' или 'failed'.
            details: Произвольные детали события.

        Returns:
            UUID созданной записи.
        """
        from chutils.audit.schema import AuditEvent

        with self._lock:
            prev_hash = self._get_last_hash()
            event = AuditEvent(
                actor=actor,
                action=action,
                target=target,
                status=status,
                details=details or {},
                prev_hash=prev_hash,
            )
            dumped = event.model_dump(mode="json")
            with self._conn.cursor() as cur:
                cur.execute(
                    _INSERT,
                    (
                        event.id,
                        dumped["timestamp"],
                        event.actor,
                        event.action,
                        event.target,
                        event.status,
                        json.dumps(event.details, default=str),
                        json.dumps(event.env, default=str),
                        event.prev_hash,
                        event.hash,
                    ),
                )
            return str(event.id)

    def verify_integrity(self) -> bool:
        """Проверяет целостность цепочки хэшей в таблице PostgreSQL.

        Returns:
            True если цепочка не нарушена.

        Raises:
            AuditIntegrityError: При обнаружении повреждённой записи.
        """
        from chutils.exceptions import AuditIntegrityError

        with self._conn.cursor() as cur:
            cur.execute(_SELECT_ALL)
            rows = cur.fetchall()

        prev_hash = ""
        for row in rows:
            (rid, actor, action, target, status, details_str,
             env_str, timestamp, stored_prev_hash, stored_hash) = row

            data: dict[str, object] = {
                "id": rid,
                "timestamp": timestamp,
                "actor": actor,
                "action": action,
                "target": target,
                "status": status,
                "details": json.loads(details_str),
                "env": json.loads(env_str),
                "prev_hash": stored_prev_hash,
            }
            expected_hash = compute_record_hash(data)

            if stored_hash != expected_hash:
                raise AuditIntegrityError(
                    "Нарушена целостность записи: hash не совпадает.",
                    record_id=rid,
                )
            if stored_prev_hash != prev_hash:
                raise AuditIntegrityError(
                    "Нарушена целостность записи: prev_hash не совпадает.",
                    record_id=rid,
                )
            prev_hash = stored_hash

        return True
