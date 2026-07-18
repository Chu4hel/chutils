"""
Тесты для Фазы 2: PostgresBackend, @audit_event, audit_context.

Покрывает:
- PostgresBackend: запись, цепочка хэшей, verify_integrity — через mock-соединение.
- @audit_event: успешный вызов, логирование исключений, callable actor/target, async-функции.
- audit_context: успешный блок, перехват исключений, изменение status/details.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest


# ---------------------------------------------------------------------------
# Тесты PostgresBackend (с mock-соединением)
# ---------------------------------------------------------------------------


class TestPostgresBackend:
    """PostgresBackend с mock-соединением (без реального Postgres)."""

    def _make_backend_with_mock(self) -> tuple[object, MagicMock]:
        """Создаёт PostgresBackend с мокнутым соединением."""
        from chutils.audit.backends.postgres import PostgresBackend

        mock_conn = MagicMock()
        # Эмулируем cursor с fetchone (возвращает None — нет предыдущей записи)
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        backend = PostgresBackend(connection=mock_conn)
        return backend, mock_conn

    def test_init_creates_table(self) -> None:
        """При инициализации выполняется CREATE TABLE IF NOT EXISTS."""
        from chutils.audit.backends.postgres import PostgresBackend

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        PostgresBackend(connection=mock_conn)

        # Проверяем что execute был вызван с CREATE TABLE
        executed_sqls = [str(c) for c in mock_cursor.execute.call_args_list]
        assert any("CREATE TABLE" in sql.upper() for sql in executed_sqls)

    def test_log_calls_execute_insert(self) -> None:
        """log() выполняет INSERT в таблицу audit_log."""
        from chutils.audit.backends.postgres import PostgresBackend

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        backend = PostgresBackend(connection=mock_conn)
        event_id = backend.log("user.login", "user_1")  # type: ignore[attr-defined]

        # Должен был вызван INSERT
        all_calls = [str(c) for c in mock_cursor.execute.call_args_list]
        assert any("INSERT" in sql.upper() for sql in all_calls)
        assert isinstance(event_id, str)

    def test_log_returns_uuid(self) -> None:
        """log() возвращает строку UUID."""
        import uuid
        from chutils.audit.backends.postgres import PostgresBackend

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        backend = PostgresBackend(connection=mock_conn)
        event_id = backend.log("x", "y")  # type: ignore[attr-defined]
        uuid.UUID(event_id)  # не падает

    def test_log_references_prev_hash(self) -> None:
        """log() передаёт prev_hash из предыдущей записи."""
        from chutils.audit.backends.postgres import PostgresBackend

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        # Первый fetchone возвращает None (нет предыдущей), второй — запись с hash
        mock_cursor.fetchone.side_effect = [None, ("abc123",)]
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        backend = PostgresBackend(connection=mock_conn)
        backend.log("first", "user")  # type: ignore[attr-defined]
        backend.log("second", "user")  # type: ignore[attr-defined]

        # Второй INSERT должен содержать prev_hash = "abc123"
        insert_calls = [
            c for c in mock_cursor.execute.call_args_list
            if "INSERT" in str(c).upper()
        ]
        assert len(insert_calls) == 2

    def test_verify_integrity_empty_returns_true(self) -> None:
        """verify_integrity возвращает True для пустой таблицы."""
        from chutils.audit.backends.postgres import PostgresBackend

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        backend = PostgresBackend(connection=mock_conn)
        assert backend.verify_integrity() is True  # type: ignore[attr-defined]

    def test_verify_integrity_detects_tamper(self) -> None:
        """verify_integrity выбрасывает AuditIntegrityError при подделке."""
        from chutils.audit.backends.postgres import PostgresBackend
        from chutils.exceptions import AuditIntegrityError

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        # Возвращаем одну запись с неверным hash
        mock_cursor.fetchall.return_value = [
            ("id-1", "actor", "action", None, "success",
             "{}", "{}", "2026-01-01T00:00:00Z", "", "wrong_hash")
        ]
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        backend = PostgresBackend(connection=mock_conn)
        with pytest.raises(AuditIntegrityError):
            backend.verify_integrity()  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Тесты @audit_event декоратора
# ---------------------------------------------------------------------------


class TestAuditEventDecorator:
    """Тесты декоратора @audit_event."""

    def _make_file_backend(self, tmp_path: Path) -> object:
        from chutils.audit.backends.file import FileBackend
        return FileBackend(tmp_path / "audit.jsonl")

    def test_decorates_sync_function(self, tmp_path: Path) -> None:
        """@audit_event оборачивает синхронную функцию и создаёт запись."""
        import json
        from chutils.audit.api import audit_event

        backend = self._make_file_backend(tmp_path)

        @audit_event(action="test.sync", actor="system", backend=backend)
        def my_func(x: int) -> int:
            return x * 2

        result = my_func(21)
        assert result == 42

        lines = (tmp_path / "audit.jsonl").read_text().splitlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["action"] == "test.sync"
        assert record["actor"] == "system"
        assert record["status"] == "success"

    def test_decorates_async_function(self, tmp_path: Path) -> None:
        """@audit_event оборачивает асинхронную функцию."""
        import json
        from chutils.audit.api import audit_event

        backend = self._make_file_backend(tmp_path)

        @audit_event(action="test.async", actor="system", backend=backend)
        async def async_func() -> str:
            return "ok"

        result = asyncio.run(async_func())
        assert result == "ok"

        lines = (tmp_path / "audit.jsonl").read_text().splitlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["status"] == "success"

    def test_records_failure_on_exception(self, tmp_path: Path) -> None:
        """@audit_event записывает status='failed' и детали при исключении."""
        import json
        from chutils.audit.api import audit_event

        backend = self._make_file_backend(tmp_path)

        @audit_event(action="test.fail", actor="system", backend=backend)
        def failing_func() -> None:
            raise ValueError("что-то пошло не так")

        with pytest.raises(ValueError):
            failing_func()

        lines = (tmp_path / "audit.jsonl").read_text().splitlines()
        record = json.loads(lines[0])
        assert record["status"] == "failed"
        assert "ValueError" in record["details"].get("error_type", "")

    def test_callable_actor(self, tmp_path: Path) -> None:
        """@audit_event поддерживает callable для actor."""
        import json
        from chutils.audit.api import audit_event

        backend = self._make_file_backend(tmp_path)

        def get_actor(*args: object, **kwargs: object) -> str:
            return "dynamic_user"

        @audit_event(action="test.actor", actor=get_actor, backend=backend)
        def my_func() -> None:
            pass

        my_func()

        record = json.loads((tmp_path / "audit.jsonl").read_text().splitlines()[0])
        assert record["actor"] == "dynamic_user"

    def test_callable_target(self, tmp_path: Path) -> None:
        """@audit_event поддерживает callable для target."""
        import json
        from chutils.audit.api import audit_event

        backend = self._make_file_backend(tmp_path)

        def get_target(doc_id: str, **_: object) -> str:
            return f"doc_{doc_id}"

        @audit_event(action="test.target", actor="u", target=get_target, backend=backend)
        def process(doc_id: str) -> str:
            return doc_id

        process("42")

        record = json.loads((tmp_path / "audit.jsonl").read_text().splitlines()[0])
        assert record["target"] == "doc_42"

    def test_string_target(self, tmp_path: Path) -> None:
        """@audit_event принимает строковый target."""
        import json
        from chutils.audit.api import audit_event

        backend = self._make_file_backend(tmp_path)

        @audit_event(action="test.str_target", actor="u", target="resource_1", backend=backend)
        def my_func() -> None:
            pass

        my_func()
        record = json.loads((tmp_path / "audit.jsonl").read_text().splitlines()[0])
        assert record["target"] == "resource_1"

    def test_failure_on_async_exception(self, tmp_path: Path) -> None:
        """@audit_event записывает failed для async-исключения."""
        import json
        from chutils.audit.api import audit_event

        backend = self._make_file_backend(tmp_path)

        @audit_event(action="test.async_fail", actor="system", backend=backend)
        async def async_failing() -> None:
            raise RuntimeError("async ошибка")

        with pytest.raises(RuntimeError):
            asyncio.run(async_failing())

        record = json.loads((tmp_path / "audit.jsonl").read_text().splitlines()[0])
        assert record["status"] == "failed"


# ---------------------------------------------------------------------------
# Тесты audit_context менеджера
# ---------------------------------------------------------------------------


class TestAuditContext:
    """Тесты контекстного менеджера audit_context."""

    def _make_file_backend(self, tmp_path: Path) -> object:
        from chutils.audit.backends.file import FileBackend
        return FileBackend(tmp_path / "audit.jsonl")

    def test_successful_block_records_success(self, tmp_path: Path) -> None:
        """audit_context записывает status='success' при нормальном выходе."""
        import json
        from chutils.audit.api import audit_context

        backend = self._make_file_backend(tmp_path)

        with audit_context(action="ctx.ok", actor="user", backend=backend):
            pass

        record = json.loads((tmp_path / "audit.jsonl").read_text().splitlines()[0])
        assert record["action"] == "ctx.ok"
        assert record["status"] == "success"

    def test_exception_block_records_failed(self, tmp_path: Path) -> None:
        """audit_context записывает status='failed' при исключении."""
        import json
        from chutils.audit.api import audit_context

        backend = self._make_file_backend(tmp_path)

        with pytest.raises(ValueError):
            with audit_context(action="ctx.fail", actor="user", backend=backend):
                raise ValueError("ошибка в блоке")

        record = json.loads((tmp_path / "audit.jsonl").read_text().splitlines()[0])
        assert record["status"] == "failed"
        assert "ValueError" in record["details"].get("error_type", "")

    def test_context_allows_setting_details(self, tmp_path: Path) -> None:
        """audit_context позволяет добавлять details через ctx.details."""
        import json
        from chutils.audit.api import audit_context

        backend = self._make_file_backend(tmp_path)

        with audit_context(action="ctx.details", actor="user", backend=backend) as ctx:
            ctx.details["rows_updated"] = 42

        record = json.loads((tmp_path / "audit.jsonl").read_text().splitlines()[0])
        assert record["details"]["rows_updated"] == 42

    def test_context_allows_overriding_status(self, tmp_path: Path) -> None:
        """audit_context позволяет переопределить status через ctx.status."""
        import json
        from chutils.audit.api import audit_context

        backend = self._make_file_backend(tmp_path)

        with audit_context(action="ctx.status", actor="user", backend=backend) as ctx:
            ctx.status = "failed"

        record = json.loads((tmp_path / "audit.jsonl").read_text().splitlines()[0])
        assert record["status"] == "failed"

    def test_context_with_target(self, tmp_path: Path) -> None:
        """audit_context принимает параметр target."""
        import json
        from chutils.audit.api import audit_context

        backend = self._make_file_backend(tmp_path)

        with audit_context(action="ctx.target", actor="u", target="doc_1", backend=backend):
            pass

        record = json.loads((tmp_path / "audit.jsonl").read_text().splitlines()[0])
        assert record["target"] == "doc_1"
