"""
Тесты для Фазы 1: AuditEvent, исключения, FileBackend, SqliteBackend.

Покрывает:
- Схему AuditEvent: валидация полей, UUID, криптографическая цепочка хэшей.
- Исключения: AuditError, AuditIntegrityError.
- FileBackend: запись JSONL, связывание хэшей, verify_integrity, tamper detection.
- SqliteBackend: аналогично FileBackend через sqlite3.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Тесты исключений
# ---------------------------------------------------------------------------

class TestAuditExceptions:
    """Тесты исключений модуля audit."""

    def test_audit_error_is_chutils_exception(self) -> None:
        """AuditError наследует ChutilsException."""
        from chutils.exceptions import AuditError, ChutilsException
        err = AuditError("тест")
        assert isinstance(err, ChutilsException)

    def test_audit_integrity_error_is_audit_error(self) -> None:
        """AuditIntegrityError наследует AuditError."""
        from chutils.exceptions import AuditIntegrityError, AuditError
        err = AuditIntegrityError("нарушение", record_id="abc")
        assert isinstance(err, AuditError)

    def test_audit_integrity_error_stores_record_id(self) -> None:
        """AuditIntegrityError сохраняет record_id в context."""
        from chutils.exceptions import AuditIntegrityError
        err = AuditIntegrityError("нарушение", record_id="abc-123")
        assert err.context.get("record_id") == "abc-123"


# ---------------------------------------------------------------------------
# Тесты схемы AuditEvent
# ---------------------------------------------------------------------------

class TestAuditEventSchema:
    """Тесты схемы AuditEvent."""

    def _make_event(self, **kwargs: object) -> object:
        from chutils.audit.schema import AuditEvent
        defaults = dict(
            actor="user_42",
            action="user.login",
            status="success",
        )
        defaults.update(kwargs)  # type: ignore[arg-type]
        return AuditEvent(**defaults)  # type: ignore[arg-type]

    def test_id_is_uuid_string(self) -> None:
        """id — строка UUID."""
        import uuid
        event = self._make_event()
        uuid.UUID(event.id)  # type: ignore[attr-defined]

    def test_timestamp_is_utc(self) -> None:
        """timestamp — datetime в UTC."""
        import datetime
        event = self._make_event()
        ts = event.timestamp  # type: ignore[attr-defined]
        assert isinstance(ts, datetime.datetime)
        assert ts.tzinfo is not None

    def test_required_fields(self) -> None:
        """Обязательные поля actor, action, status присутствуют."""
        event = self._make_event(actor="sys", action="db.query", status="failed")
        assert event.actor == "sys"  # type: ignore[attr-defined]
        assert event.action == "db.query"  # type: ignore[attr-defined]
        assert event.status == "failed"  # type: ignore[attr-defined]

    def test_optional_target_defaults_none(self) -> None:
        """target по умолчанию None."""
        event = self._make_event()
        assert event.target is None  # type: ignore[attr-defined]

    def test_optional_target_can_be_set(self) -> None:
        """target принимает строковое значение."""
        event = self._make_event(target="document_99")
        assert event.target == "document_99"  # type: ignore[attr-defined]

    def test_details_defaults_empty_dict(self) -> None:
        """details по умолчанию пустой dict."""
        event = self._make_event()
        assert event.details == {}  # type: ignore[attr-defined]

    def test_env_contains_hostname_and_pid(self) -> None:
        """env автоматически включает hostname и pid."""
        event = self._make_event()
        env = event.env  # type: ignore[attr-defined]
        assert "hostname" in env
        assert "pid" in env

    def test_env_contains_thread_name(self) -> None:
        """env содержит thread_name текущего потока."""
        event = self._make_event()
        assert "thread_name" in event.env  # type: ignore[attr-defined]

    def test_prev_hash_defaults_empty_string(self) -> None:
        """prev_hash по умолчанию пустая строка (первая запись)."""
        event = self._make_event()
        assert event.prev_hash == ""  # type: ignore[attr-defined]

    def test_hash_is_sha256_hex(self) -> None:
        """hash — SHA-256 hex-строка длиной 64 символа."""
        event = self._make_event()
        assert isinstance(event.hash, str)  # type: ignore[attr-defined]
        assert len(event.hash) == 64  # type: ignore[attr-defined]

    def test_hash_includes_prev_hash(self) -> None:
        """hash зависит от prev_hash — разные prev_hash дают разные hash."""
        from chutils.audit.schema import AuditEvent
        e1 = AuditEvent(actor="u", action="a", status="success", prev_hash="")
        e2 = AuditEvent(actor="u", action="a", status="success", prev_hash="x" * 64)
        assert e1.hash != e2.hash

    def test_hash_deterministic_for_same_data(self) -> None:
        """hash воспроизводим для одних и тех же данных."""
        from chutils.audit.schema import AuditEvent
        import datetime

        fixed_ts = datetime.datetime(2025, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)
        fixed_id = "00000000-0000-0000-0000-000000000001"
        e1 = AuditEvent(
            id=fixed_id, timestamp=fixed_ts,
            actor="u", action="a", status="success",
            prev_hash="abc", env={"hostname": "h", "pid": 1, "thread_name": "main"},
        )
        e2 = AuditEvent(
            id=fixed_id, timestamp=fixed_ts,
            actor="u", action="a", status="success",
            prev_hash="abc", env={"hostname": "h", "pid": 1, "thread_name": "main"},
        )
        assert e1.hash == e2.hash

    def test_to_jsonl_roundtrip(self) -> None:
        """to_jsonl() → from_jsonl() восстанавливает исходный объект."""
        from chutils.audit.schema import AuditEvent
        event = AuditEvent(actor="u", action="a", status="success")
        line = event.to_jsonl()
        restored = AuditEvent.from_jsonl(line)
        assert restored.id == event.id
        assert restored.hash == event.hash
        assert restored.actor == event.actor


# ---------------------------------------------------------------------------
# Тесты FileBackend
# ---------------------------------------------------------------------------

class TestFileBackend:
    """Тесты FileBackend — JSONL-файл."""

    def _make_backend(self, tmp_path: Path) -> object:
        from chutils.audit.backends.file import FileBackend
        return FileBackend(tmp_path / "audit.jsonl")

    def test_append_creates_file(self, tmp_path: Path) -> None:
        """append создаёт файл при первой записи."""
        backend = self._make_backend(tmp_path)
        backend.log("user.login", "user_1", status="success")  # type: ignore[attr-defined]
        assert (tmp_path / "audit.jsonl").exists()

    def test_first_record_has_empty_prev_hash(self, tmp_path: Path) -> None:
        """Первая запись имеет пустой prev_hash."""
        backend = self._make_backend(tmp_path)
        backend.log("user.login", "user_1")  # type: ignore[attr-defined]
        line = (tmp_path / "audit.jsonl").read_text().strip()
        record = json.loads(line)
        assert record["prev_hash"] == ""

    def test_second_record_references_first_hash(self, tmp_path: Path) -> None:
        """Вторая запись ссылается на hash первой."""
        backend = self._make_backend(tmp_path)
        backend.log("a", "u1")  # type: ignore[attr-defined]
        backend.log("b", "u2")  # type: ignore[attr-defined]
        lines = (tmp_path / "audit.jsonl").read_text().strip().splitlines()
        first = json.loads(lines[0])
        second = json.loads(lines[1])
        assert second["prev_hash"] == first["hash"]

    def test_verify_integrity_ok(self, tmp_path: Path) -> None:
        """verify_integrity возвращает True для нетронутого лога."""
        backend = self._make_backend(tmp_path)
        for i in range(5):
            backend.log(f"action.{i}", "actor")  # type: ignore[attr-defined]
        assert backend.verify_integrity() is True  # type: ignore[attr-defined]

    def test_verify_integrity_detects_tamper(self, tmp_path: Path) -> None:
        """verify_integrity выбрасывает AuditIntegrityError при изменении записи."""
        from chutils.exceptions import AuditIntegrityError
        backend = self._make_backend(tmp_path)
        backend.log("action.1", "actor")  # type: ignore[attr-defined]
        backend.log("action.2", "actor")  # type: ignore[attr-defined]

        # Портим первую запись
        path = tmp_path / "audit.jsonl"
        lines = path.read_text().splitlines()
        record = json.loads(lines[0])
        record["actor"] = "hacker"
        lines[0] = json.dumps(record)
        path.write_text("\n".join(lines))

        with pytest.raises(AuditIntegrityError):
            backend.verify_integrity()  # type: ignore[attr-defined]

    def test_verify_integrity_single_record_ok(self, tmp_path: Path) -> None:
        """verify_integrity работает с единственной записью."""
        backend = self._make_backend(tmp_path)
        backend.log("x", "y")  # type: ignore[attr-defined]
        assert backend.verify_integrity() is True  # type: ignore[attr-defined]

    def test_verify_integrity_empty_log_ok(self, tmp_path: Path) -> None:
        """verify_integrity для пустого лога возвращает True."""
        backend = self._make_backend(tmp_path)
        assert backend.verify_integrity() is True  # type: ignore[attr-defined]

    def test_log_with_details(self, tmp_path: Path) -> None:
        """Детали события сохраняются в записи."""
        backend = self._make_backend(tmp_path)
        backend.log("login", "u", details={"ip": "127.0.0.1"})  # type: ignore[attr-defined]
        line = (tmp_path / "audit.jsonl").read_text().strip()
        record = json.loads(line)
        assert record["details"]["ip"] == "127.0.0.1"

    def test_thread_safety(self, tmp_path: Path) -> None:
        """Параллельная запись из нескольких потоков не ломает цепочку."""
        backend = self._make_backend(tmp_path)
        errors: list[Exception] = []

        def writer() -> None:
            try:
                for _ in range(5):
                    backend.log("concurrent", "thread")  # type: ignore[attr-defined]
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert backend.verify_integrity() is True  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Тесты SqliteBackend
# ---------------------------------------------------------------------------

class TestSqliteBackend:
    """Тесты SqliteBackend — хранение в SQLite через sqlite3."""

    def _make_backend(self, tmp_path: Path) -> object:
        from chutils.audit.backends.sqlite import SqliteBackend
        return SqliteBackend(tmp_path / "audit.db")

    def test_log_creates_table(self, tmp_path: Path) -> None:
        """Первый log создаёт таблицу audit_log в базе."""
        backend = self._make_backend(tmp_path)
        backend.log("login", "user_1")  # type: ignore[attr-defined]
        conn = sqlite3.connect(tmp_path / "audit.db")
        cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='audit_log'")
        assert cur.fetchone() is not None
        conn.close()

    def test_first_record_has_empty_prev_hash(self, tmp_path: Path) -> None:
        """Первая запись имеет пустой prev_hash."""
        backend = self._make_backend(tmp_path)
        backend.log("action", "actor")  # type: ignore[attr-defined]
        conn = sqlite3.connect(tmp_path / "audit.db")
        row = conn.execute("SELECT prev_hash FROM audit_log").fetchone()
        assert row[0] == ""
        conn.close()

    def test_chain_links_correctly(self, tmp_path: Path) -> None:
        """Хэши записей связаны в цепочку."""
        backend = self._make_backend(tmp_path)
        backend.log("a", "u")  # type: ignore[attr-defined]
        backend.log("b", "u")  # type: ignore[attr-defined]
        conn = sqlite3.connect(tmp_path / "audit.db")
        rows = conn.execute("SELECT hash, prev_hash FROM audit_log ORDER BY rowid").fetchall()
        assert rows[1][1] == rows[0][0]  # prev_hash[1] == hash[0]
        conn.close()

    def test_verify_integrity_ok(self, tmp_path: Path) -> None:
        """verify_integrity возвращает True для нетронутой БД."""
        backend = self._make_backend(tmp_path)
        for i in range(5):
            backend.log(f"action.{i}", "actor")  # type: ignore[attr-defined]
        assert backend.verify_integrity() is True  # type: ignore[attr-defined]

    def test_verify_integrity_detects_tamper(self, tmp_path: Path) -> None:
        """verify_integrity выбрасывает AuditIntegrityError при изменении записи."""
        from chutils.exceptions import AuditIntegrityError
        backend = self._make_backend(tmp_path)
        backend.log("x", "u")  # type: ignore[attr-defined]
        backend.log("y", "u")  # type: ignore[attr-defined]

        conn = sqlite3.connect(tmp_path / "audit.db")
        conn.execute("UPDATE audit_log SET actor='hacker' WHERE rowid=1")
        conn.commit()
        conn.close()

        with pytest.raises(AuditIntegrityError):
            backend.verify_integrity()  # type: ignore[attr-defined]

    def test_verify_integrity_empty_db_ok(self, tmp_path: Path) -> None:
        """verify_integrity для пустой БД возвращает True."""
        backend = self._make_backend(tmp_path)
        assert backend.verify_integrity() is True  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Тесты ленивого импорта
# ---------------------------------------------------------------------------

def test_lazy_import_no_pydantic(monkeypatch: pytest.MonkeyPatch) -> None:
    """Тест проверки ленивого импорта при отсутствии Pydantic."""
    import sys

    # Сохраняем оригинальное состояние
    orig_pydantic = sys.modules.get("pydantic")

    to_delete = [
        "chutils", "chutils.audit", "chutils.audit.schema",
        "chutils.audit.backends", "chutils.audit.backends.file",
        "chutils.audit.backends.sqlite", "chutils.audit.backends.postgres",
        "chutils.audit.api"
    ]

    try:
        # Замаскируем pydantic как отсутствующий
        monkeypatch.setitem(sys.modules, "pydantic", None)  # type: ignore[assignment]
        for mod in to_delete:
            sys.modules.pop(mod, None)

        # Импорт chutils не должен приводить к падению
        import chutils

        # chutils.AuditEvent должен быть None, так как Pydantic отсутствует
        assert chutils.AuditEvent is None
    finally:
        # Восстанавливаем
        if orig_pydantic is not None:
            sys.modules["pydantic"] = orig_pydantic
        else:
            sys.modules.pop("pydantic", None)

        # Снова сбрасываем кэш, чтобы вернуть нормальный импорт в остальных тестах
        for mod in to_delete:
            sys.modules.pop(mod, None)
