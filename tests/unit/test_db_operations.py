"""
Тесты для Фазы 2: управление сессиями, транзакциями и жизненным циклом chutils.db.

Проверяет:
- Контекстный менеджер session() возвращает AsyncSession.
- Контекстный менеджер transaction() выполняет commit при успехе.
- Контекстный менеджер transaction() выполняет rollback при исключении.
- Метод ping() возвращает True при успешном соединении.
- Метод ping() возвращает False при ошибке соединения.
- Метод register_cleanup() регистрирует функцию в chutils.lifecycle.
"""
import asyncio
from unittest.mock import patch

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from chutils.db import DatabaseManager


# ---------------------------------------------------------------------------
# Фикстуры
# ---------------------------------------------------------------------------


@pytest.fixture
def in_memory_db_url() -> str:
    """URL для SQLite in-memory БД с aiosqlite."""
    return "sqlite+aiosqlite:///:memory:"


@pytest.fixture
def db_manager(in_memory_db_url: str) -> DatabaseManager:
    """Создаёт DatabaseManager с SQLite in-memory БД."""
    return DatabaseManager(database_url=in_memory_db_url)


# ---------------------------------------------------------------------------
# Вспомогательная функция — создать тестовую таблицу
# ---------------------------------------------------------------------------


async def _create_test_table(db: DatabaseManager) -> None:
    """Создаёт тестовую таблицу items в БД."""
    async with db.session() as session:
        await session.execute(text(
            "CREATE TABLE IF NOT EXISTS items "
            "(id INTEGER PRIMARY KEY, name TEXT NOT NULL)"
        ))
        await session.commit()


# ---------------------------------------------------------------------------
# Тесты session()
# ---------------------------------------------------------------------------


class TestSessionContextManager:
    """Тесты контекстного менеджера session()."""

    @pytest.mark.asyncio
    async def test_session_returns_async_session(self, db_manager: DatabaseManager) -> None:
        """Проверяет, что session() возвращает экземпляр AsyncSession."""
        async with db_manager.session() as session:
            assert isinstance(session, AsyncSession)

    @pytest.mark.asyncio
    async def test_session_can_execute_query(self, db_manager: DatabaseManager) -> None:
        """Проверяет выполнение запроса внутри session()."""
        async with db_manager.session() as session:
            result = await session.execute(text("SELECT 1"))
            value = result.scalar_one()
            assert value == 1

    @pytest.mark.asyncio
    async def test_multiple_sessions_are_independent(self, db_manager: DatabaseManager) -> None:
        """Проверяет, что несколько вызовов session() не конфликтуют."""
        async with db_manager.session() as s1:
            async with db_manager.session() as s2:
                r1 = await s1.execute(text("SELECT 1"))
                r2 = await s2.execute(text("SELECT 2"))
                assert r1.scalar_one() == 1
                assert r2.scalar_one() == 2


# ---------------------------------------------------------------------------
# Тесты transaction()
# ---------------------------------------------------------------------------


class TestTransactionContextManager:
    """Тесты контекстного менеджера transaction()."""

    @pytest.mark.asyncio
    async def test_transaction_commits_on_success(self, db_manager: DatabaseManager) -> None:
        """Проверяет автоматический commit при успешном выходе из блока."""
        await _create_test_table(db_manager)

        async with db_manager.transaction() as session:
            await session.execute(text("INSERT INTO items (name) VALUES ('test_item')"))

        # Проверяем, что данные сохранились
        async with db_manager.session() as session:
            result = await session.execute(text("SELECT COUNT(*) FROM items"))
            count = result.scalar_one()
            assert count == 1

    @pytest.mark.asyncio
    async def test_transaction_rollbacks_on_exception(self, db_manager: DatabaseManager) -> None:
        """Проверяет автоматический rollback при исключении внутри блока."""
        await _create_test_table(db_manager)

        with pytest.raises(ValueError):
            async with db_manager.transaction() as session:
                await session.execute(
                    text("INSERT INTO items (name) VALUES ('should_not_persist')")
                )
                raise ValueError("Принудительная ошибка для теста rollback")

        # Проверяем, что данные НЕ сохранились
        async with db_manager.session() as session:
            result = await session.execute(text("SELECT COUNT(*) FROM items"))
            count = result.scalar_one()
            assert count == 0

    @pytest.mark.asyncio
    async def test_transaction_returns_async_session(self, db_manager: DatabaseManager) -> None:
        """Проверяет, что transaction() возвращает AsyncSession."""
        async with db_manager.transaction() as session:
            assert isinstance(session, AsyncSession)

    @pytest.mark.asyncio
    async def test_multiple_inserts_in_one_transaction(self, db_manager: DatabaseManager) -> None:
        """Проверяет несколько операций в одной транзакции."""
        await _create_test_table(db_manager)

        async with db_manager.transaction() as session:
            await session.execute(text("INSERT INTO items (name) VALUES ('item_1')"))
            await session.execute(text("INSERT INTO items (name) VALUES ('item_2')"))
            await session.execute(text("INSERT INTO items (name) VALUES ('item_3')"))

        async with db_manager.session() as session:
            result = await session.execute(text("SELECT COUNT(*) FROM items"))
            assert result.scalar_one() == 3

    @pytest.mark.asyncio
    async def test_exception_does_not_leak_data(self, db_manager: DatabaseManager) -> None:
        """Проверяет, что исключение не приводит к частичной записи данных."""
        await _create_test_table(db_manager)

        # Первая успешная транзакция
        async with db_manager.transaction() as session:
            await session.execute(text("INSERT INTO items (name) VALUES ('committed')"))

        # Прерванная транзакция
        with pytest.raises(RuntimeError):
            async with db_manager.transaction() as session:
                await session.execute(
                    text("INSERT INTO items (name) VALUES ('rolled_back')")
                )
                raise RuntimeError("Ошибка в середине транзакции")

        # Должна остаться только первая запись
        async with db_manager.session() as session:
            result = await session.execute(text("SELECT name FROM items"))
            names = [row[0] for row in result.fetchall()]
            assert names == ["committed"]
            assert "rolled_back" not in names


# ---------------------------------------------------------------------------
# Тесты ping()
# ---------------------------------------------------------------------------


class TestPing:
    """Тесты метода ping()."""

    @pytest.mark.asyncio
    async def test_ping_returns_true_on_success(self, db_manager: DatabaseManager) -> None:
        """Проверяет, что ping() возвращает True при работающем соединении."""
        result = await db_manager.ping()
        assert result is True

    @pytest.mark.asyncio
    async def test_ping_returns_false_on_error(self) -> None:
        """Проверяет, что ping() возвращает False при ошибке соединения."""
        db = DatabaseManager(database_url="sqlite+aiosqlite:///:memory:")

        # AsyncEngine.connect — read-only в SQLAlchemy 2.0, патчим через модуль
        from unittest.mock import AsyncMock
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(side_effect=OSError("Симуляция ошибки соединения"))

        with patch("chutils.db.AsyncEngine.connect", return_value=mock_ctx):
            result = await db.ping()
            assert result is False


# ---------------------------------------------------------------------------
# Тесты register_cleanup()
# ---------------------------------------------------------------------------


class TestRegisterCleanup:
    """Тесты метода register_cleanup()."""

    def test_register_cleanup_uses_lifecycle_register(
            self, db_manager: DatabaseManager
    ) -> None:
        """Проверяет, что register_cleanup() вызывает chutils.lifecycle.register_cleanup."""
        registered_funcs: list[object] = []

        def capture_func(func: object) -> object:
            registered_funcs.append(func)
            return func

        with patch("chutils.lifecycle.register_cleanup", side_effect=capture_func):
            db_manager.register_cleanup()

        assert len(registered_funcs) == 1
        # Зарегистрированная функция должна быть корутинной
        assert asyncio.iscoroutinefunction(registered_funcs[0])

    def test_register_cleanup_can_be_called_multiple_times(
            self, db_manager: DatabaseManager
    ) -> None:
        """Проверяет, что повторный вызов register_cleanup() не вызывает ошибку."""
        with patch("chutils.lifecycle.register_cleanup") as mock_reg:
            db_manager.register_cleanup()
            db_manager.register_cleanup()
            assert mock_reg.call_count == 2

    @pytest.mark.asyncio
    async def test_registered_callback_disposes_engine(
            self, db_manager: DatabaseManager
    ) -> None:
        """Проверяет, что зарегистрированный колбэк вызывает engine.dispose()."""
        from unittest.mock import AsyncMock

        registered_funcs: list[object] = []

        def capture_func(func: object) -> object:
            registered_funcs.append(func)
            return func

        with patch("chutils.lifecycle.register_cleanup", side_effect=capture_func):
            db_manager.register_cleanup()

        assert len(registered_funcs) == 1
        dispose_coro = registered_funcs[0]

        # AsyncEngine.dispose — read-only в SQLAlchemy 2.0, патчим через класс
        mock_dispose = AsyncMock(return_value=None)
        with patch("chutils.db.AsyncEngine.dispose", mock_dispose):
            await dispose_coro()  # type: ignore[operator]
            mock_dispose.assert_called_once()
