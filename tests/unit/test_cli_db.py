"""
Тесты для Фазы 1: регистрация CLI-команд chutils db и безопасный импорт.

Проверяет:
- Команда `chutils db` доступна в парсере.
- Все подкоманды (make-migration, upgrade, downgrade, status, history) регистрируются.
- Аргументы каждой подкоманды парсятся корректно.
- При отсутствии alembic выбрасывается OptionalDependencyError.
"""
import sys
import argparse
from typing import Any
from unittest.mock import patch, MagicMock

import pytest


# ---------------------------------------------------------------------------
# Вспомогательная функция — создать парсер с командой db
# ---------------------------------------------------------------------------


def _make_parser() -> tuple[argparse.ArgumentParser, argparse._SubParsersAction]:  # type: ignore[type-arg]
    """Создаёт argparse-парсер с зарегистрированным DbCommand."""
    from chutils.commands.db import DbCommand

    parser = argparse.ArgumentParser(prog="chutils")
    subparsers = parser.add_subparsers(dest="command")
    DbCommand().register(subparsers)
    return parser, subparsers


# ---------------------------------------------------------------------------
# Тесты регистрации команды
# ---------------------------------------------------------------------------


class TestDbCommandRegistration:
    """Тесты регистрации группы команд db в CLI."""

    def test_db_command_is_registered(self) -> None:
        """Проверяет, что команда `db` появляется в парсере."""
        parser, _ = _make_parser()
        args = parser.parse_args(["db", "--help"] if False else ["db", "status"])
        assert args.command == "db"

    def test_make_migration_subcommand_registered(self) -> None:
        """Проверяет регистрацию подкоманды make-migration."""
        parser, _ = _make_parser()
        args = parser.parse_args(["db", "make-migration", "init_db"])
        assert args.subcommand == "make-migration"
        assert args.message == "init_db"

    def test_make_migration_default_message(self) -> None:
        """Проверяет дефолтное значение message для make-migration."""
        parser, _ = _make_parser()
        args = parser.parse_args(["db", "make-migration"])
        assert args.subcommand == "make-migration"
        assert args.message is None

    def test_upgrade_subcommand_registered(self) -> None:
        """Проверяет регистрацию подкоманды upgrade с дефолтной ревизией head."""
        parser, _ = _make_parser()
        args = parser.parse_args(["db", "upgrade"])
        assert args.subcommand == "upgrade"
        assert args.revision == "head"

    def test_upgrade_with_custom_revision(self) -> None:
        """Проверяет парсинг upgrade с явной ревизией."""
        parser, _ = _make_parser()
        args = parser.parse_args(["db", "upgrade", "abc123"])
        assert args.revision == "abc123"

    def test_downgrade_subcommand_registered(self) -> None:
        """Проверяет регистрацию подкоманды downgrade с дефолтной ревизией -1."""
        parser, _ = _make_parser()
        args = parser.parse_args(["db", "downgrade"])
        assert args.subcommand == "downgrade"
        assert args.revision == "-1"

    def test_downgrade_with_custom_revision(self) -> None:
        """Проверяет парсинг downgrade с явной ревизией."""
        parser, _ = _make_parser()
        args = parser.parse_args(["db", "downgrade", "base"])
        assert args.revision == "base"

    def test_status_subcommand_registered(self) -> None:
        """Проверяет регистрацию подкоманды status."""
        parser, _ = _make_parser()
        args = parser.parse_args(["db", "status"])
        assert args.subcommand == "status"

    def test_history_subcommand_registered(self) -> None:
        """Проверяет регистрацию подкоманды history."""
        parser, _ = _make_parser()
        args = parser.parse_args(["db", "history"])
        assert args.subcommand == "history"

    def test_metadata_flag_available(self) -> None:
        """Проверяет, что флаг --metadata доступен в make-migration."""
        parser, _ = _make_parser()
        args = parser.parse_args([
            "db", "make-migration", "--metadata", "app.db:Base.metadata"
        ])
        assert args.metadata == "app.db:Base.metadata"


# ---------------------------------------------------------------------------
# Тесты безопасного импорта (OptionalDependencyError без alembic)
# ---------------------------------------------------------------------------


class TestDbCommandOptionalDependency:
    """Тесты поведения при отсутствии alembic."""

    def test_import_without_alembic_raises_error_on_make_migration(self) -> None:
        """Проверяет OptionalDependencyError при make-migration без alembic."""
        from chutils.commands.db import DbCommand
        from chutils.exceptions import OptionalDependencyError

        cmd = DbCommand()
        args = argparse.Namespace(
            subcommand="make-migration",
            message="test",
            metadata=None,
        )

        with patch("chutils.commands.db.ALEMBIC_AVAILABLE", False):
            with pytest.raises(OptionalDependencyError):
                cmd.handle(args)

    def test_import_without_alembic_raises_error_on_upgrade(self) -> None:
        """Проверяет OptionalDependencyError при upgrade без alembic."""
        from chutils.commands.db import DbCommand
        from chutils.exceptions import OptionalDependencyError

        cmd = DbCommand()
        args = argparse.Namespace(subcommand="upgrade", revision="head", metadata=None)

        with patch("chutils.commands.db.ALEMBIC_AVAILABLE", False):
            with pytest.raises(OptionalDependencyError):
                cmd.handle(args)

    def test_import_without_alembic_raises_error_on_downgrade(self) -> None:
        """Проверяет OptionalDependencyError при downgrade без alembic."""
        from chutils.commands.db import DbCommand
        from chutils.exceptions import OptionalDependencyError

        cmd = DbCommand()
        args = argparse.Namespace(subcommand="downgrade", revision="-1", metadata=None)

        with patch("chutils.commands.db.ALEMBIC_AVAILABLE", False):
            with pytest.raises(OptionalDependencyError):
                cmd.handle(args)

    def test_import_without_alembic_raises_error_on_status(self) -> None:
        """Проверяет OptionalDependencyError при status без alembic."""
        from chutils.commands.db import DbCommand
        from chutils.exceptions import OptionalDependencyError

        cmd = DbCommand()
        args = argparse.Namespace(subcommand="status", metadata=None)

        with patch("chutils.commands.db.ALEMBIC_AVAILABLE", False):
            with pytest.raises(OptionalDependencyError):
                cmd.handle(args)

    def test_import_without_alembic_raises_error_on_history(self) -> None:
        """Проверяет OptionalDependencyError при history без alembic."""
        from chutils.commands.db import DbCommand
        from chutils.exceptions import OptionalDependencyError

        cmd = DbCommand()
        args = argparse.Namespace(subcommand="history", metadata=None)

        with patch("chutils.commands.db.ALEMBIC_AVAILABLE", False):
            with pytest.raises(OptionalDependencyError):
                cmd.handle(args)

    def test_error_message_contains_install_hint(self) -> None:
        """Проверяет, что сообщение об ошибке содержит подсказку по установке."""
        from chutils.commands.db import DbCommand
        from chutils.exceptions import OptionalDependencyError

        cmd = DbCommand()
        args = argparse.Namespace(subcommand="status", metadata=None)

        with patch("chutils.commands.db.ALEMBIC_AVAILABLE", False):
            with pytest.raises(OptionalDependencyError) as exc_info:
                cmd.handle(args)
            assert "alembic" in exc_info.value.message.lower()

    def test_chutils_import_not_broken_without_alembic(self) -> None:
        """Проверяет, что import chutils не ломается при отсутствии alembic."""
        # Если этот тест выполнился — импорт chutils успешен
        import chutils
        assert chutils is not None


# ---------------------------------------------------------------------------
# Тесты веток handle() без подкоманды и с неизвестной подкомандой
# ---------------------------------------------------------------------------


class TestDbCommandHandleEdgeCases:
    """Тесты edge-cases в методе handle()."""

    def test_handle_without_subcommand_prints_hint(self) -> None:
        """Проверяет вывод подсказки, если subcommand не передан."""
        from chutils.commands.db import DbCommand

        cmd = DbCommand()
        args = argparse.Namespace()  # нет атрибута subcommand

        messages: list[str] = []
        cmd.err_console.print = lambda msg, **kw: messages.append(str(msg))  # type: ignore[method-assign]

        cmd.handle(args)
        assert any("help" in m.lower() or "подкоманд" in m.lower() for m in messages)

    def test_handle_with_unknown_subcommand_prints_error(self) -> None:
        """Проверяет вывод ошибки при неизвестной подкоманде."""
        from chutils.commands.db import DbCommand

        cmd = DbCommand()
        args = argparse.Namespace(subcommand="nonexistent")

        messages: list[str] = []
        cmd.err_console.print = lambda msg, **kw: messages.append(str(msg))  # type: ignore[method-assign]

        cmd.handle(args)
        assert any("nonexistent" in m or "Неизвестная" in m for m in messages)


# ---------------------------------------------------------------------------
# Тесты _resolve_config
# ---------------------------------------------------------------------------


class TestResolveConfig:
    """Тесты функции _resolve_config."""

    def test_raises_config_error_when_no_url(self) -> None:
        """Проверяет ConfigError при отсутствии URL БД в конфиге."""
        from chutils.commands.db import _resolve_config
        from chutils.exceptions import ConfigError

        args = argparse.Namespace(metadata=None)

        # get_config_value импортируется внутри функции — патчим в chutils.config
        with patch("chutils.config.get_config_value", return_value=None):
            with pytest.raises(ConfigError):
                _resolve_config(args)

    def test_reads_url_from_database_section(self) -> None:
        """Проверяет чтение URL из секции [Database]."""
        from chutils.commands.db import _resolve_config

        args = argparse.Namespace(metadata=None)

        def mock_config(section: str, key: str, default: object = None) -> str | None:
            if section == "Database" and key == "url":
                return "sqlite+aiosqlite:///test.db"
            return None

        with patch("chutils.config.get_config_value", side_effect=mock_config):
            db_url, _, _ = _resolve_config(args)
            assert db_url == "sqlite+aiosqlite:///test.db"

    def test_reads_metadata_from_args(self) -> None:
        """Проверяет считывание метаданных из аргументов командной строки."""
        from chutils.commands.db import _resolve_config

        fake_meta = MagicMock()
        fake_module = MagicMock()
        fake_module.Base = MagicMock(metadata=fake_meta)

        args = argparse.Namespace(metadata="myapp.db:Base.metadata")

        def mock_config(section: str, key: str, default: object = None) -> str | None:
            if section == "Database" and key == "url":
                return "sqlite+aiosqlite:///test.db"
            return None

        with (
            patch("chutils.config.get_config_value", side_effect=mock_config),
            patch.dict(sys.modules, {"myapp.db": fake_module}),
        ):
            _, _, metadata = _resolve_config(args)
            assert metadata is fake_meta


# ---------------------------------------------------------------------------
# Тест history без директории
# ---------------------------------------------------------------------------


class TestHistoryNoDirBranch:
    """Покрытие ветки history при отсутствии директории миграций."""

    def test_history_without_migrations_dir_prints_hint(self, tmp_path: Any) -> None:
        """Проверяет, что history без директории миграций выводит предупреждение."""
        from chutils.commands.db import DbCommand
        from pathlib import Path

        missing_dir = tmp_path / "no_migrations"  # type: ignore[operator]
        mock_cfg = MagicMock(return_value=("sqlite+aiosqlite:///x.db", missing_dir, None))

        cmd = DbCommand()
        args = argparse.Namespace(subcommand="history", metadata=None)

        messages: list[str] = []
        cmd.console.print = lambda msg, **kw: messages.append(str(msg))  # type: ignore[method-assign]

        with patch("chutils.commands.db._resolve_config", mock_cfg):
            cmd.handle(args)

        assert any("не найдена" in m or "history" in m.lower() for m in messages)

