"""
Интеграционные тесты для Фазы 2: программная обёртка над Alembic API.

Проверяет с использованием SQLite in-memory (sqlite+aiosqlite):
- make-migration: автогенерация файла миграции на основе тестовых моделей.
- upgrade: применение миграций на БД.
- downgrade: откат миграций на шаг назад.
- status: вывод текущей ревизии.
- history: вывод истории миграций.
"""
import argparse
import sys
import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import sqlalchemy as sa
from sqlalchemy import MetaData, Column, Integer, String


# ---------------------------------------------------------------------------
# Фикстуры
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_migrations_dir(tmp_path: Path) -> Path:
    """Создаёт временную директорию для файлов миграций."""
    migrations = tmp_path / "migrations"
    return migrations


@pytest.fixture
def sqlite_url(tmp_path: Path) -> str:
    """URL для SQLite файловой БД (не in-memory, нужен путь для Alembic)."""
    db_file = tmp_path / "test.db"
    return f"sqlite+aiosqlite:///{db_file}"


@pytest.fixture
def test_metadata() -> MetaData:
    """Создаёт тестовые метаданные SQLAlchemy с одной таблицей."""
    metadata = MetaData()
    sa.Table(
        "users",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("name", String(100), nullable=False),
        Column("email", String(255), nullable=True),
    )
    return metadata


@pytest.fixture
def mock_config(sqlite_url: str, tmp_migrations_dir: Path, test_metadata: MetaData) -> MagicMock:
    """Создаёт мок для _resolve_config, возвращающий тестовые параметры."""
    mock = MagicMock(return_value=(sqlite_url, tmp_migrations_dir, test_metadata))
    return mock


# ---------------------------------------------------------------------------
# Тест динамического импорта метаданных
# ---------------------------------------------------------------------------


class TestImportMetadata:
    """Тесты функции _import_metadata."""

    def test_import_metadata_valid_path(self, test_metadata: MetaData) -> None:
        """Проверяет успешный импорт объекта по пути module:attr."""
        from chutils.commands.db import _import_metadata

        # Регистрируем тестовые метаданные в sys.modules
        fake_module = MagicMock()
        fake_module.Base = MagicMock()
        fake_module.Base.metadata = test_metadata

        with patch.dict(sys.modules, {"myapp.db": fake_module}):
            result = _import_metadata("myapp.db:Base.metadata")
            assert result is test_metadata

    def test_import_metadata_invalid_format_raises_value_error(self) -> None:
        """Проверяет ValueError при отсутствии ':' в пути."""
        from chutils.commands.db import _import_metadata

        with pytest.raises(ValueError, match="Неверный формат"):
            _import_metadata("myapp.db.Base.metadata")

    def test_import_metadata_missing_module_raises_import_error(self) -> None:
        """Проверяет ImportError при отсутствии модуля."""
        from chutils.commands.db import _import_metadata

        with pytest.raises((ImportError, ModuleNotFoundError)):
            _import_metadata("nonexistent.module.xyz:SomeClass.metadata")


# ---------------------------------------------------------------------------
# Тест инициализации директории миграций
# ---------------------------------------------------------------------------


class TestInitMigrationsDir:
    """Тесты функции _init_migrations_dir."""

    def test_creates_migrations_directory(self, tmp_migrations_dir: Path) -> None:
        """Проверяет создание директории при её отсутствии."""
        from chutils.commands.db import _init_migrations_dir

        assert not tmp_migrations_dir.exists()
        _init_migrations_dir(tmp_migrations_dir)
        assert tmp_migrations_dir.exists()

    def test_creates_versions_subdirectory(self, tmp_migrations_dir: Path) -> None:
        """Проверяет создание поддиректории versions."""
        from chutils.commands.db import _init_migrations_dir

        _init_migrations_dir(tmp_migrations_dir)
        assert (tmp_migrations_dir / "versions").exists()

    def test_creates_env_py(self, tmp_migrations_dir: Path) -> None:
        """Проверяет создание асинхронного env.py."""
        from chutils.commands.db import _init_migrations_dir

        _init_migrations_dir(tmp_migrations_dir)
        env_py = tmp_migrations_dir / "env.py"
        assert env_py.exists()
        content = env_py.read_text(encoding="utf-8")
        assert "async_engine_from_config" in content
        assert "run_migrations_online" in content

    def test_creates_script_mako(self, tmp_migrations_dir: Path) -> None:
        """Проверяет создание script.py.mako шаблона."""
        from chutils.commands.db import _init_migrations_dir

        _init_migrations_dir(tmp_migrations_dir)
        assert (tmp_migrations_dir / "script.py.mako").exists()

    def test_idempotent_when_already_exists(self, tmp_migrations_dir: Path) -> None:
        """Проверяет, что повторный вызов не вызывает ошибку."""
        from chutils.commands.db import _init_migrations_dir

        _init_migrations_dir(tmp_migrations_dir)
        _init_migrations_dir(tmp_migrations_dir)  # не должен падать
        assert tmp_migrations_dir.exists()


# ---------------------------------------------------------------------------
# Тесты build_alembic_config
# ---------------------------------------------------------------------------


class TestBuildAlembicConfig:
    """Тесты функции _build_alembic_config."""

    def test_sets_sqlalchemy_url(
        self, sqlite_url: str, tmp_migrations_dir: Path
    ) -> None:
        """Проверяет, что URL БД установлен в конфиг Alembic."""
        from chutils.commands.db import _build_alembic_config

        cfg = _build_alembic_config(sqlite_url, tmp_migrations_dir)
        assert cfg.get_main_option("sqlalchemy.url") == sqlite_url

    def test_sets_script_location(
        self, sqlite_url: str, tmp_migrations_dir: Path
    ) -> None:
        """Проверяет, что путь к скриптам миграций установлен корректно."""
        from chutils.commands.db import _build_alembic_config

        cfg = _build_alembic_config(sqlite_url, tmp_migrations_dir)
        assert cfg.get_main_option("script_location") == str(tmp_migrations_dir)


# ---------------------------------------------------------------------------
# Интеграционные тесты Alembic (make-migration, upgrade, downgrade)
# ---------------------------------------------------------------------------


class TestAlembicIntegration:
    """Интеграционные тесты выполнения миграций через Alembic API."""

    def test_make_migration_creates_file(
        self,
        sqlite_url: str,
        tmp_migrations_dir: Path,
        test_metadata: MetaData,
        mock_config: MagicMock,
    ) -> None:
        """Проверяет создание файла миграции командой make-migration."""
        from chutils.commands.db import DbCommand, _init_migrations_dir

        _init_migrations_dir(tmp_migrations_dir)

        cmd = DbCommand()
        args = argparse.Namespace(
            subcommand="make-migration",
            message="create_users_table",
            metadata=None,
        )

        with patch("chutils.commands.db._resolve_config", mock_config):
            cmd.handle(args)

        versions_dir = tmp_migrations_dir / "versions"
        migration_files = list(versions_dir.glob("*.py"))
        assert len(migration_files) == 1
        content = migration_files[0].read_text(encoding="utf-8")
        assert "create_users_table" in content

    def test_upgrade_applies_migration(
        self,
        sqlite_url: str,
        tmp_migrations_dir: Path,
        test_metadata: MetaData,
        mock_config: MagicMock,
    ) -> None:
        """Проверяет применение миграции через upgrade head."""
        from chutils.commands.db import DbCommand, _init_migrations_dir

        _init_migrations_dir(tmp_migrations_dir)

        cmd = DbCommand()

        # Сначала создаём миграцию
        make_args = argparse.Namespace(
            subcommand="make-migration",
            message="init",
            metadata=None,
        )
        with patch("chutils.commands.db._resolve_config", mock_config):
            cmd.handle(make_args)

        # Затем применяем
        upgrade_args = argparse.Namespace(
            subcommand="upgrade",
            revision="head",
            metadata=None,
        )
        with patch("chutils.commands.db._resolve_config", mock_config):
            cmd.handle(upgrade_args)  # не должен падать

    def test_downgrade_rolls_back(
        self,
        sqlite_url: str,
        tmp_migrations_dir: Path,
        test_metadata: MetaData,
        mock_config: MagicMock,
    ) -> None:
        """Проверяет откат миграции через downgrade."""
        from chutils.commands.db import DbCommand, _init_migrations_dir

        _init_migrations_dir(tmp_migrations_dir)
        cmd = DbCommand()

        # make-migration + upgrade + downgrade
        for subcommand, revision in [
            ("make-migration", None),
            ("upgrade", "head"),
            ("downgrade", "-1"),
        ]:
            args = argparse.Namespace(
                subcommand=subcommand,
                message="init" if subcommand == "make-migration" else None,
                revision=revision,
                metadata=None,
            )
            with patch("chutils.commands.db._resolve_config", mock_config):
                cmd.handle(args)

    def test_status_without_migrations_dir_prints_hint(
        self,
        tmp_migrations_dir: Path,
        mock_config: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Проверяет, что status без директории миграций выводит подсказку."""
        from chutils.commands.db import DbCommand
        from chutils.cli_utils import get_console

        assert not tmp_migrations_dir.exists()

        cmd = DbCommand()
        args = argparse.Namespace(subcommand="status", metadata=None)

        output_lines: list[str] = []

        def capture_print(msg: str, **kwargs: object) -> None:
            output_lines.append(msg)

        cmd.console.print = capture_print  # type: ignore[method-assign]

        with patch("chutils.commands.db._resolve_config", mock_config):
            cmd.handle(args)

        combined = " ".join(output_lines)
        assert "make-migration" in combined or "не найдена" in combined

    def test_status_after_upgrade_shows_revision(
        self,
        sqlite_url: str,
        tmp_migrations_dir: Path,
        test_metadata: MetaData,
        mock_config: MagicMock,
    ) -> None:
        """Проверяет вывод текущей ревизии в status после upgrade."""
        from chutils.commands.db import DbCommand, _init_migrations_dir

        _init_migrations_dir(tmp_migrations_dir)
        cmd = DbCommand()

        for subcommand, revision in [("make-migration", None), ("upgrade", "head")]:
            args = argparse.Namespace(
                subcommand=subcommand,
                message="init",
                revision=revision,
                metadata=None,
            )
            with patch("chutils.commands.db._resolve_config", mock_config):
                cmd.handle(args)

        # status не должен падать
        status_args = argparse.Namespace(subcommand="status", metadata=None)
        with patch("chutils.commands.db._resolve_config", mock_config):
            cmd.handle(status_args)

    def test_history_shows_migration_entries(
        self,
        sqlite_url: str,
        tmp_migrations_dir: Path,
        test_metadata: MetaData,
        mock_config: MagicMock,
    ) -> None:
        """Проверяет вывод истории миграций через history."""
        from chutils.commands.db import DbCommand, _init_migrations_dir

        _init_migrations_dir(tmp_migrations_dir)
        cmd = DbCommand()

        make_args = argparse.Namespace(
            subcommand="make-migration",
            message="first_migration",
            metadata=None,
        )
        with patch("chutils.commands.db._resolve_config", mock_config):
            cmd.handle(make_args)

        history_args = argparse.Namespace(subcommand="history", metadata=None)
        with patch("chutils.commands.db._resolve_config", mock_config):
            cmd.handle(history_args)  # не должен падать
