# ruff: noqa: E402
"""
Модуль chutils.db — готовый менеджер подключений к реляционным БД.

Предоставляет класс :class:`DatabaseManager` для управления асинхронным
соединением с базой данных через SQLAlchemy 2.0.

Зависимости — опциональные. При их отсутствии вызов модуля
завершается с :exc:`~chutils.exceptions.OptionalDependencyError`.

Пример использования::

    from chutils.db import DatabaseManager

    db = DatabaseManager(database_url="sqlite+aiosqlite:///:memory:")

    async with db.transaction() as session:
        result = await session.execute(text("SELECT 1"))

    await db.ping()
    db.register_cleanup()
"""

from __future__ import annotations

import importlib.util

from chutils.exceptions import ConfigError, OptionalDependencyError

# ---------------------------------------------------------------------------
# Проверка наличия sqlalchemy (опциональная зависимость)
# ---------------------------------------------------------------------------
_HAS_SQLALCHEMY = (
        importlib.util.find_spec("sqlalchemy") is not None
        and importlib.util.find_spec("sqlalchemy.ext.asyncio") is not None
)

if not _HAS_SQLALCHEMY:
    raise OptionalDependencyError(
        "Модуль 'chutils.db' требует установленной библиотеки 'sqlalchemy' с поддержкой asyncio.\n"
        "Установите её с помощью команды: pip install chutils[db]",
        dependency="sqlalchemy",
        hint="Выполните: pip install chutils[db]",
    )

# ---------------------------------------------------------------------------
# Импорты SQLAlchemy (безопасны, т.к. выше уже проверено наличие)
# ---------------------------------------------------------------------------
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, AsyncIterator, cast

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy import text

from chutils.config import get_config_value

if TYPE_CHECKING:
    pass


class DatabaseManager:
    """Менеджер подключений к реляционным БД на основе SQLAlchemy 2.0 (async).

    Инкапсулирует создание асинхронного движка, фабрику сессий,
    контекстные менеджеры для транзакций и интеграцию с жизненным
    циклом chutils.

    Зависимости (опциональные): ``sqlalchemy``, ``asyncpg``, ``aiosqlite``.

    Args:
        database_url: URL подключения к БД. Если не передан,
            считывается из конфигурации chutils в следующем порядке:

            1. Секция ``[Database]``, ключ ``url`` или ``database_url``.
            2. Секция ``[Secrets]``, ключ ``database_url``.

        echo: Включить вывод SQL-запросов в консоль (для отладки).
            По умолчанию ``False``.
        **engine_kwargs: Дополнительные параметры, передаваемые
            в :func:`sqlalchemy.ext.asyncio.create_async_engine`.

    Raises:
        ConfigError: Если URL подключения не задан ни явно,
            ни в конфигурации.

    Example:
        Базовое использование::

            db = DatabaseManager(database_url="sqlite+aiosqlite:///:memory:")

            async with db.transaction() as session:
                await session.execute(text("INSERT INTO ..."))

        Автоматическое чтение URL из конфига::

            # config.ini:
            # [Database]
            # url = postgresql+asyncpg://user:pass@localhost/mydb

            db = DatabaseManager()
    """

    def __init__(
            self,
            database_url: str | None = None,
            echo: bool = False,
            **engine_kwargs: object,
    ) -> None:
        """Инициализирует DatabaseManager и создаёт асинхронный движок.

        Args:
            database_url: URL подключения к БД. Если ``None``, URL
                считывается из конфигурации chutils.
            echo: Если ``True``, все SQL-запросы выводятся в stdout.
            **engine_kwargs: Дополнительные именованные аргументы для
                :func:`~sqlalchemy.ext.asyncio.create_async_engine`.

        Raises:
            ConfigError: Если URL не найден ни в параметрах,
                ни в конфигурации.
        """
        resolved_url = database_url or self._resolve_url_from_config()

        if not resolved_url:
            raise ConfigError(
                "Не задан URL подключения к базе данных. "
                "Передайте 'database_url' явно или задайте его в конфигурации "
                "в секции [Database] (ключи 'url' / 'database_url') "
                "либо в секции [Secrets] (ключ 'database_url').",
                hint="Пример: DatabaseManager(database_url='sqlite+aiosqlite:///:memory:')",
            )

        self._engine: AsyncEngine = create_async_engine(
            resolved_url,
            echo=echo,
            **engine_kwargs,
        )
        self._session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
            bind=self._engine,
            expire_on_commit=False,
            class_=AsyncSession,
        )

    # ------------------------------------------------------------------
    # Внутренние методы
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_url_from_config() -> str | None:
        """Пытается считать URL из конфигурации chutils.

        Порядок поиска:
        1. ``[Database]`` → ``url``
        2. ``[Database]`` → ``database_url``
        3. ``[Secrets]`` → ``database_url``

        Returns:
            URL подключения или ``None``, если не найден.
        """
        url = get_config_value("Database", "url")
        if url:
            return cast(str, url)

        url = get_config_value("Database", "database_url")
        if url:
            return cast(str, url)

        url = get_config_value("Secrets", "database_url")
        return cast(str | None, url)

    # ------------------------------------------------------------------
    # Публичный API: управление сессиями
    # ------------------------------------------------------------------

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """Асинхронный контекстный менеджер, возвращающий сессию SQLAlchemy.

        Сессия не управляет транзакцией автоматически — для этого
        используйте :meth:`transaction`.

        Yields:
            Открытая :class:`~sqlalchemy.ext.asyncio.AsyncSession`.

        Example::

            async with db.session() as session:
                result = await session.execute(text("SELECT 1"))
        """
        async with self._session_factory() as async_session:
            yield async_session

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[AsyncSession]:
        """Асинхронный контекстный менеджер для транзакций.

        Автоматически вызывает :meth:`commit` по выходу из блока
        или :meth:`rollback` при возникновении исключения.

        Yields:
            :class:`~sqlalchemy.ext.asyncio.AsyncSession` в рамках активной транзакции.

        Raises:
            Exception: Любое исключение из тела блока ``async with``
                инициирует откат транзакции и пробрасывается дальше.

        Example::

            async with db.transaction() as session:
                session.add(MyModel(name="test"))
        """
        async with self._session_factory() as async_session:
            async with async_session.begin():
                yield async_session

    # ------------------------------------------------------------------
    # Публичный API: health check и lifecycle
    # ------------------------------------------------------------------

    async def ping(self) -> bool:
        """Проверяет доступность подключения к базе данных.

        Выполняет простой запрос ``SELECT 1`` и возвращает результат проверки.

        Returns:
            ``True`` если соединение успешно, ``False`` — при любой ошибке.

        Example::

            is_alive = await db.ping()
            if not is_alive:
                logger.error("База данных недоступна!")
        """
        try:
            async with self._engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    def register_cleanup(self) -> None:
        """Регистрирует метод закрытия движка в менеджере жизненного цикла chutils.

        После вызова этого метода движок (и пул соединений) будет
        корректно освобождён при завершении приложения через
        :func:`~chutils.lifecycle.register_cleanup`.

        Example::

            db = DatabaseManager(database_url="postgresql+asyncpg://...")
            db.register_cleanup()  # автоматически закроет пул при shutdown
        """
        from chutils.lifecycle import register_cleanup

        async def _dispose_engine() -> None:
            await self._engine.dispose()

        _dispose_engine.__name__ = f"dispose_engine_{id(self)}"
        register_cleanup(_dispose_engine)


__all__ = ["DatabaseManager"]
