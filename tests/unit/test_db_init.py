"""
Тесты для Фазы 1: ленивый импорт, инициализация и безопасный экспорт chutils.db.

Проверяет:
- OptionalDependencyError при отсутствии sqlalchemy.
- Корректную инициализацию DatabaseManager с явным URL.
- Чтение URL из конфигурации chutils (секции [Database] и [Secrets]).
- ConfigError, если URL не найден ни в параметрах, ни в конфигурации.
"""
import importlib
import sys
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------


def _clear_db_modules() -> None:
    """Удаляет модули chutils.db из кэша sys.modules для чистого импорта."""
    to_delete = [m for m in sys.modules if m == "chutils.db"]
    for m in to_delete:
        sys.modules.pop(m, None)


# ---------------------------------------------------------------------------
# Тесты безопасного импорта (OptionalDependencyError)
# ---------------------------------------------------------------------------


class TestDbImportSafety:
    """Тесты безопасного импорта при отсутствии зависимостей."""

    def test_import_without_sqlalchemy_raises_optional_dependency_error(self) -> None:
        """Проверяет, что импорт без sqlalchemy вызывает OptionalDependencyError."""
        _clear_db_modules()

        with patch.dict(sys.modules, {"sqlalchemy": None, "sqlalchemy.ext.asyncio": None}):
            from chutils.exceptions import OptionalDependencyError

            with pytest.raises(OptionalDependencyError) as exc_info:
                importlib.import_module("chutils.db")

            error_message = str(exc_info.value)
            assert "sqlalchemy" in error_message.lower()
            assert "chutils[db]" in error_message

    def test_error_message_contains_install_hint(self) -> None:
        """Проверяет, что сообщение об ошибке содержит подсказку по установке."""
        _clear_db_modules()

        with patch.dict(sys.modules, {"sqlalchemy": None, "sqlalchemy.ext.asyncio": None}):
            from chutils.exceptions import OptionalDependencyError

            with pytest.raises(OptionalDependencyError) as exc_info:
                importlib.import_module("chutils.db")

            error_message = str(exc_info.value)
            assert "pip install" in error_message or "chutils[db]" in error_message


# ---------------------------------------------------------------------------
# Тесты инициализации DatabaseManager с явным URL
# ---------------------------------------------------------------------------


class TestDatabaseManagerInit:
    """Тесты инициализации DatabaseManager."""

    def test_init_with_explicit_url(self) -> None:
        """Проверяет корректную инициализацию с явным database_url."""
        mock_engine = MagicMock()
        mock_session_factory = MagicMock()

        # Патчим имена прямо в пространстве имён модуля chutils.db
        with (
            patch("chutils.db.create_async_engine", return_value=mock_engine) as mock_create,
            patch("chutils.db.async_sessionmaker", return_value=mock_session_factory),
        ):
            from chutils.db import DatabaseManager

            db = DatabaseManager(database_url="sqlite+aiosqlite:///:memory:")

            assert db is not None
            mock_create.assert_called_once()
            call_args = mock_create.call_args
            assert "sqlite+aiosqlite:///:memory:" in str(call_args)

    def test_init_with_echo_false_by_default(self) -> None:
        """Проверяет, что echo=False по умолчанию."""
        mock_engine = MagicMock()
        mock_session_factory = MagicMock()

        with (
            patch("chutils.db.create_async_engine", return_value=mock_engine) as mock_create,
            patch("chutils.db.async_sessionmaker", return_value=mock_session_factory),
        ):
            from chutils.db import DatabaseManager

            DatabaseManager(database_url="sqlite+aiosqlite:///:memory:")

            call_kwargs = mock_create.call_args[1]
            assert call_kwargs.get("echo") is False

    def test_init_with_echo_true(self) -> None:
        """Проверяет передачу echo=True в движок."""
        mock_engine = MagicMock()
        mock_session_factory = MagicMock()

        with (
            patch("chutils.db.create_async_engine", return_value=mock_engine) as mock_create,
            patch("chutils.db.async_sessionmaker", return_value=mock_session_factory),
        ):
            from chutils.db import DatabaseManager

            DatabaseManager(database_url="sqlite+aiosqlite:///:memory:", echo=True)

            call_kwargs = mock_create.call_args[1]
            assert call_kwargs.get("echo") is True


# ---------------------------------------------------------------------------
# Тесты чтения URL из конфигурации
# ---------------------------------------------------------------------------


class TestDatabaseManagerConfigReading:
    """Тесты чтения URL подключения из конфигурации chutils."""

    def test_reads_url_from_database_section(self) -> None:
        """Проверяет считывание URL из секции [Database], ключ url."""
        mock_engine = MagicMock()
        mock_session_factory = MagicMock()

        def mock_get_config_value(section: str, key: str, default: str | None = None) -> str | None:
            if section == "Database" and key == "url":
                return "postgresql+asyncpg://user:pass@localhost/db"
            return default

        with (
            patch("chutils.db.create_async_engine", return_value=mock_engine) as mock_create,
            patch("chutils.db.async_sessionmaker", return_value=mock_session_factory),
            patch("chutils.db.get_config_value", side_effect=mock_get_config_value),
        ):
            from chutils.db import DatabaseManager

            db = DatabaseManager()
            assert db is not None
            call_args_str = str(mock_create.call_args)
            assert "postgresql+asyncpg://user:pass@localhost/db" in call_args_str

    def test_reads_url_from_database_section_database_url_key(self) -> None:
        """Проверяет считывание URL из секции [Database], ключ database_url (второй fallback)."""
        mock_engine = MagicMock()
        mock_session_factory = MagicMock()

        def mock_get_config_value(section: str, key: str, default: str | None = None) -> str | None:
            # url возвращает None, database_url — нет
            if section == "Database" and key == "database_url":
                return "postgresql+asyncpg://user:pass@db-key-host/db"
            return default

        with (
            patch("chutils.db.create_async_engine", return_value=mock_engine) as mock_create,
            patch("chutils.db.async_sessionmaker", return_value=mock_session_factory),
            patch("chutils.db.get_config_value", side_effect=mock_get_config_value),
        ):
            from chutils.db import DatabaseManager

            db = DatabaseManager()
            assert db is not None
            call_args_str = str(mock_create.call_args)
            assert "postgresql+asyncpg://user:pass@db-key-host/db" in call_args_str

    def test_reads_url_from_secrets_section_as_fallback(self) -> None:
        """Проверяет fallback-поиск URL в секции [Secrets]."""
        mock_engine = MagicMock()
        mock_session_factory = MagicMock()

        def mock_get_config_value(section: str, key: str, default: str | None = None) -> str | None:
            if section == "Secrets" and key == "database_url":
                return "postgresql+asyncpg://user:pass@secrets-host/db"
            return default

        with (
            patch("chutils.db.create_async_engine", return_value=mock_engine) as mock_create,
            patch("chutils.db.async_sessionmaker", return_value=mock_session_factory),
            patch("chutils.db.get_config_value", side_effect=mock_get_config_value),
        ):
            from chutils.db import DatabaseManager

            db = DatabaseManager()
            assert db is not None
            call_args_str = str(mock_create.call_args)
            assert "postgresql+asyncpg://user:pass@secrets-host/db" in call_args_str

    def test_raises_config_error_when_url_not_found(self) -> None:
        """Проверяет выброс ConfigError, если URL не найден ни в конфиге, ни в параметрах."""
        mock_engine = MagicMock()
        mock_session_factory = MagicMock()

        with (
            patch("chutils.db.create_async_engine", return_value=mock_engine),
            patch("chutils.db.async_sessionmaker", return_value=mock_session_factory),
            patch("chutils.db.get_config_value", return_value=None),
        ):
            from chutils.db import DatabaseManager
            from chutils.exceptions import ConfigError

            with pytest.raises(ConfigError):
                DatabaseManager()

    def test_explicit_url_takes_precedence_over_config(self) -> None:
        """Проверяет, что явный URL имеет приоритет над конфигурацией."""
        mock_engine = MagicMock()
        mock_session_factory = MagicMock()
        explicit_url = "sqlite+aiosqlite:///explicit.db"

        with (
            patch("chutils.db.create_async_engine", return_value=mock_engine) as mock_create,
            patch("chutils.db.async_sessionmaker", return_value=mock_session_factory),
            patch("chutils.db.get_config_value", return_value="postgresql+asyncpg://config-host/db"),
        ):
            from chutils.db import DatabaseManager

            DatabaseManager(database_url=explicit_url)
            call_args_str = str(mock_create.call_args)
            assert explicit_url in call_args_str
            assert "config-host" not in call_args_str


# ---------------------------------------------------------------------------
# Тест ленивого экспорта через __init__.py
# ---------------------------------------------------------------------------


class TestLazyExport:
    """Тесты ленивой загрузки через публичный API."""

    def test_database_manager_accessible_via_chutils(self) -> None:
        """Проверяет доступность DatabaseManager через chutils.DatabaseManager."""
        import chutils

        dm_class = chutils.DatabaseManager
        assert dm_class is not None

    def test_db_module_accessible_via_chutils(self) -> None:
        """Проверяет доступность модуля chutils.db через chutils.db."""
        import chutils

        db_mod = chutils.db
        assert db_mod is not None
        assert hasattr(db_mod, "DatabaseManager")
