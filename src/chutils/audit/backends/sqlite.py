"""SqliteBackend — хранение журнала аудита в SQLite через стандартную библиотеку sqlite3."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from pathlib import Path

from chutils.audit._hash import compute_record_hash
from chutils.audit.backends.base import BaseAuditBackend
from chutils.fs import ensure_dir

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS audit_log (
    id          TEXT NOT NULL,
    timestamp   TEXT NOT NULL,
    actor       TEXT NOT NULL,
    action      TEXT NOT NULL,
    target      TEXT,
    status      TEXT NOT NULL,
    details     TEXT NOT NULL,
    env         TEXT NOT NULL,
    prev_hash   TEXT NOT NULL,
    hash        TEXT NOT NULL
)
"""


class SqliteBackend(BaseAuditBackend):
    """Бэкенд хранения событий аудита в таблице SQLite.

    Использует только стандартную библиотеку sqlite3 — без SQLAlchemy.
    Записи связаны в криптографическую цепочку через поле prev_hash.
    Запись потокобезопасна (threading.Lock + WAL режим SQLite).

    Args:
        path: Путь к файлу БД (будет создан при первой записи).
    """

    def __init__(self, path: str | Path) -> None:
        """Инициализирует SqliteBackend и создаёт таблицу audit_log если она отсутствует.

        Args:
            path: Путь к файлу SQLite БД (будет создан автоматически).
        """
        self._path = Path(path)
        self._lock = threading.Lock()
        self._ensure_table()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _ensure_table(self) -> None:
        ensure_dir(self._path.parent)
        with self._connect() as conn:
            conn.execute(_CREATE_TABLE)

    def _get_last_hash(self, conn: sqlite3.Connection) -> str:
        """Возвращает hash последней записи или '' если таблица пуста."""
        row = conn.execute(
            "SELECT hash FROM audit_log ORDER BY rowid DESC LIMIT 1"
        ).fetchone()
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
        """Добавляет событие в таблицу audit_log.

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
            with self._connect() as conn:
                prev_hash = self._get_last_hash(conn)
                event = AuditEvent(
                    actor=actor,
                    action=action,
                    target=target,
                    status=status,
                    details=details or {},
                    prev_hash=prev_hash,
                )
                # Используем model_dump(mode="json") чтобы timestamp
                # имел тот же формат что был использован при вычислении hash
                dumped = event.model_dump(mode="json")
                conn.execute(
                    """INSERT INTO audit_log
                       (id, timestamp, actor, action, target, status, details, env, prev_hash, hash)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
            return event.id

    def verify_integrity(self) -> bool:
        """Проверяет целостность цепочки хэшей в таблице audit_log.

        Returns:
            True если цепочка не нарушена.

        Raises:
            AuditIntegrityError: При обнаружении повреждённой записи.
        """
        from chutils.exceptions import AuditIntegrityError

        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, actor, action, target, status, details, env, "
                "timestamp, prev_hash, hash FROM audit_log ORDER BY rowid"
            ).fetchall()

        prev_hash = ""
        for row in rows:
            (rid, actor, action, target, status, details_str,
             env_str, timestamp, stored_prev_hash, stored_hash) = row

            # Строим dict в том же порядке что AuditEvent.model_dump(mode="json")
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
                    "Нарушена целостность записи: prev_hash не совпадает с предыдущим hash.",
                    record_id=rid,
                )
            prev_hash = stored_hash

        return True
