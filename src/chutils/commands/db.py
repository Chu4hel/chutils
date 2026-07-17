"""
Команды CLI для управления миграциями базы данных через Alembic.

Группа `chutils db` предоставляет обёртку над Alembic API для:
- Создания новых автогенерируемых миграций (make-migration).
- Применения миграций до указанной ревизии (upgrade).
- Отката миграций (downgrade).
- Просмотра текущего статуса (status).
- Просмотра истории миграций (history).

Зависимость от `alembic` является **опциональной**. При её отсутствии
все команды группы `db` выбрасывают `OptionalDependencyError`.

Пример использования::

    chutils db status
    chutils db make-migration "create users table" --metadata app.db:Base.metadata
    chutils db upgrade
    chutils db downgrade -1
"""
from __future__ import annotations

import argparse
import importlib
import importlib.util
import sys
from pathlib import Path
from typing import Any

from chutils.commands.base import BaseCommand
from chutils.cli_utils import get_console

# ---------------------------------------------------------------------------
# Проверка опциональной зависимости alembic
# ---------------------------------------------------------------------------

ALEMBIC_AVAILABLE: bool = importlib.util.find_spec("alembic") is not None

# Шаблон асинхронного env.py для Alembic
_ASYNC_ENV_PY_TEMPLATE = '''\
"""Alembic async env.py — автоматически сгенерирован chutils."""
from __future__ import annotations

import asyncio
from logging.config import fileConfig

from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy import pool

from alembic import context

# Объект метаданных моделей передаётся из chutils при вызове команд
target_metadata = context.config.attributes.get("target_metadata", None)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def run_migrations_offline() -> None:
    """Запуск миграций в offline-режиме (без подключения к БД)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Any) -> None:
    """Выполняет миграции через полученное соединение."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Запуск миграций в асинхронном режиме."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    """Запуск миграций в online-режиме (async)."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
'''


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------


def _require_alembic() -> None:
    """Проверяет наличие alembic и выбрасывает OptionalDependencyError при его отсутствии.

    Raises:
        OptionalDependencyError: Если пакет alembic не установлен.
    """
    if not ALEMBIC_AVAILABLE:
        from chutils.exceptions import OptionalDependencyError

        raise OptionalDependencyError(
            package="alembic",
            message="Для работы команд 'chutils db' требуется пакет alembic.",
            hint="Установите alembic: pip install chutils[db]",
        )


def _init_migrations_dir(migrations_path: Path) -> None:
    """Инициализирует директорию миграций с асинхронным env.py, если она не существует.

    Args:
        migrations_path: Путь к директории для хранения файлов миграций.
    """
    console = get_console()

    if not migrations_path.exists():
        from chutils.fs import ensure_dir, atomic_write

        ensure_dir(migrations_path)
        ensure_dir(migrations_path / "versions")

        env_py = migrations_path / "env.py"
        atomic_write(env_py, _ASYNC_ENV_PY_TEMPLATE)

        mako_content = (
            '{"""${message}\n\nRevision ID: ${up_revision}\n'
            'Revises: ${down_revision | comma,n}\n'
            'Create Date: ${create_date}\n\n"""}\n'
            'from alembic import op\nimport sqlalchemy as sa\n'
            '${imports if imports else ""}\n\n'
            'revision = ${repr(up_revision)}\n'
            'down_revision = ${repr(down_revision)}\n'
            'branch_labels = ${repr(branch_labels)}\n'
            'depends_on = ${repr(depends_on)}\n\n\n'
            'def upgrade() -> None:\n    ${upgrades if upgrades else "pass"}\n\n\n'
            'def downgrade() -> None:\n    ${downgrades if downgrades else "pass"}\n'
        )
        script_mako = migrations_path / "script.py.mako"
        atomic_write(script_mako, mako_content)

        console.print(
            f"[green]✓[/green] Директория миграций инициализирована: {migrations_path}"
        )


def _import_metadata(metadata_path: str) -> Any:
    """Динамически импортирует объект MetaData по пути вида 'module.path:AttrName'.

    Args:
        metadata_path: Строка вида ``app.db:Base.metadata``.

    Returns:
        Объект MetaData из указанного модуля.

    Raises:
        ImportError: Если модуль не найден или атрибут не существует.
        ValueError: Если путь имеет неверный формат.
    """
    if ":" not in metadata_path:
        raise ValueError(
            f"Неверный формат --metadata. Ожидается 'module.path:AttrName', "
            f"получено: '{metadata_path}'"
        )

    module_path, attr_chain = metadata_path.split(":", 1)
    module = importlib.import_module(module_path)
    obj: Any = module
    for attr in attr_chain.split("."):
        obj = getattr(obj, attr)
    return obj


def _resolve_config(args: argparse.Namespace) -> tuple[str, Path, Any | None]:
    """Считывает database_url, migrations_path и metadata из конфига/аргументов.

    Args:
        args: Аргументы командной строки.

    Returns:
        Кортеж (database_url, migrations_path, metadata_obj | None).

    Raises:
        chutils.exceptions.ConfigError: Если URL базы данных не найден.
    """
    from chutils.config import get_config_value
    from chutils.exceptions import ConfigError

    # database_url
    db_url = (
        get_config_value("Database", "url")
        or get_config_value("Database", "database_url")
        or get_config_value("Secrets", "database_url")
    )
    if not db_url:
        raise ConfigError(
            message="URL базы данных не найден в конфигурации.",
            hint="Добавьте 'url' в секцию [Database] файла config.yml или .env",
        )

    # migrations_path
    migrations_str = get_config_value("Database", "migrations_path") or "migrations"
    migrations_path = Path(migrations_str)

    # metadata (из аргументов или конфига)
    metadata_str: str | None = getattr(args, "metadata", None) or get_config_value(
        "Database", "metadata"
    )
    metadata_obj: Any | None = None
    if metadata_str:
        metadata_obj = _import_metadata(metadata_str)

    return db_url, migrations_path, metadata_obj


def _build_alembic_config(db_url: str, migrations_path: Path) -> Any:
    """Создаёт объект alembic.config.Config в памяти без alembic.ini.

    Args:
        db_url: URL подключения к базе данных.
        migrations_path: Директория с файлами миграций.

    Returns:
        Настроенный объект alembic.config.Config.
    """
    from alembic.config import Config  # type: ignore[import-not-found]

    cfg = Config()
    cfg.set_main_option("script_location", str(migrations_path))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


# ---------------------------------------------------------------------------
# Команда DbCommand
# ---------------------------------------------------------------------------


class DbCommand(BaseCommand):
    """Группа команд для управления миграциями базы данных через Alembic.

    Предоставляет удобную обёртку над Alembic API с автоматической
    инициализацией директории миграций и динамическим построением
    конфигурации без необходимости создавать alembic.ini вручную.
    """

    def register(self, subparsers: argparse._SubParsersAction[Any]) -> None:  # type: ignore[type-arg]
        """Регистрирует команду db и все её подкоманды в argparse.

        Args:
            subparsers: Объект subparsers для добавления команды.
        """
        db_parser = subparsers.add_parser(
            "db",
            help="Управление миграциями базы данных",
            description=(
                "Команды для управления миграциями БД через Alembic. "
                "Требует установки: pip install chutils[db]"
            ),
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""Примеры использования:
  chutils db status
  chutils db make-migration "create users" --metadata app.db:Base.metadata
  chutils db upgrade
  chutils db downgrade -1
""",
        )
        db_parser.set_defaults(handler=self.handle)
        db_sub = db_parser.add_subparsers(
            dest="subcommand",
            help="Доступные действия",
        )

        # make-migration
        mm_parser = db_sub.add_parser(
            "make-migration",
            help="Создать новую автогенерируемую миграцию",
            description="Сравнивает модели с текущим состоянием БД и генерирует файл миграции.",
        )
        mm_parser.add_argument(
            "message",
            nargs="?",
            default=None,
            help="Сообщение (описание) для файла миграции",
        )
        mm_parser.add_argument(
            "--metadata",
            default=None,
            metavar="MODULE:ATTR",
            help="Путь к MetaData моделей, например 'app.db:Base.metadata'",
        )

        # upgrade
        up_parser = db_sub.add_parser(
            "upgrade",
            help="Применить миграции до указанной ревизии",
        )
        up_parser.add_argument(
            "revision",
            nargs="?",
            default="head",
            help="Целевая ревизия (по умолчанию: head)",
        )
        up_parser.add_argument(
            "--metadata",
            default=None,
            metavar="MODULE:ATTR",
            help="Путь к MetaData моделей",
        )

        # downgrade
        down_parser = db_sub.add_parser(
            "downgrade",
            help="Откатить миграции до указанной ревизии",
        )
        down_parser.add_argument(
            "revision",
            nargs="?",
            default="-1",
            help="Целевая ревизия (по умолчанию: -1)",
        )
        down_parser.add_argument(
            "--metadata",
            default=None,
            metavar="MODULE:ATTR",
        )

        # status
        db_sub.add_parser(
            "status",
            help="Показать текущую версию БД",
            description="Выводит текущую примененную версию и общий статус миграций.",
        )

        # history
        db_sub.add_parser(
            "history",
            help="Показать историю всех миграций",
        )

    def handle(self, args: argparse.Namespace) -> None:
        """Диспетчер выполнения подкоманды db.

        Args:
            args: Распарсенные аргументы командной строки.

        Raises:
            OptionalDependencyError: Если alembic не установлен.
        """
        _require_alembic()

        subcommand: str | None = getattr(args, "subcommand", None)
        if subcommand is None:
            self.err_console.print(
                "[yellow]Укажите подкоманду. Используйте 'chutils db --help'.[/yellow]"
            )
            return

        dispatch: dict[str, Any] = {
            "make-migration": self._make_migration,
            "upgrade": self._upgrade,
            "downgrade": self._downgrade,
            "status": self._status,
            "history": self._history,
        }
        handler = dispatch.get(subcommand)
        if handler is None:
            self.err_console.print(
                f"[red]Неизвестная подкоманда: {subcommand}[/red]"
            )
            return
        handler(args)

    # ------------------------------------------------------------------
    # Реализации подкоманд
    # ------------------------------------------------------------------

    def _make_migration(self, args: argparse.Namespace) -> None:
        """Создаёт новую автогенерируемую миграцию Alembic.

        Args:
            args: Аргументы с полями message и metadata.
        """
        from alembic import command  # type: ignore[import-not-found]

        db_url, migrations_path, metadata_obj = _resolve_config(args)
        _init_migrations_dir(migrations_path)

        cfg = _build_alembic_config(db_url, migrations_path)
        if metadata_obj is not None:
            cfg.attributes["target_metadata"] = metadata_obj

        message: str = getattr(args, "message", None) or "auto_migration"
        self.console.print(
            f"[cyan]Генерация миграции:[/cyan] {message}"
        )
        command.revision(cfg, message=message, autogenerate=True)
        self.console.print("[green]✓[/green] Миграция создана.")

    def _upgrade(self, args: argparse.Namespace) -> None:
        """Применяет миграции до указанной ревизии.

        Args:
            args: Аргументы с полем revision.
        """
        from alembic import command  # type: ignore[import-not-found]

        db_url, migrations_path, metadata_obj = _resolve_config(args)
        _init_migrations_dir(migrations_path)

        cfg = _build_alembic_config(db_url, migrations_path)
        if metadata_obj is not None:
            cfg.attributes["target_metadata"] = metadata_obj

        revision: str = getattr(args, "revision", "head")
        self.console.print(f"[cyan]Применение миграций до:[/cyan] {revision}")
        command.upgrade(cfg, revision)
        self.console.print("[green]✓[/green] Миграции применены.")

    def _downgrade(self, args: argparse.Namespace) -> None:
        """Откатывает миграции до указанной ревизии.

        Args:
            args: Аргументы с полем revision.
        """
        from alembic import command  # type: ignore[import-not-found]

        db_url, migrations_path, _metadata_obj = _resolve_config(args)

        cfg = _build_alembic_config(db_url, migrations_path)
        revision: str = getattr(args, "revision", "-1")
        self.console.print(f"[cyan]Откат миграций до:[/cyan] {revision}")
        command.downgrade(cfg, revision)
        self.console.print("[green]✓[/green] Откат выполнен.")

    def _status(self, args: argparse.Namespace) -> None:
        """Выводит текущий статус миграций.

        Args:
            args: Аргументы командной строки (не используются).
        """
        from alembic import command  # type: ignore[import-not-found]

        db_url, migrations_path, _metadata_obj = _resolve_config(args)

        if not migrations_path.exists():
            self.console.print(
                "[yellow]Директория миграций не найдена.[/yellow] "
                "Запустите 'chutils db make-migration' для создания первой миграции."
            )
            return

        cfg = _build_alembic_config(db_url, migrations_path)
        self.console.print("[cyan]Текущий статус миграций:[/cyan]")
        command.current(cfg, verbose=True)

    def _history(self, args: argparse.Namespace) -> None:
        """Выводит полную историю миграций.

        Args:
            args: Аргументы командной строки (не используются).
        """
        from alembic import command  # type: ignore[import-not-found]

        db_url, migrations_path, _metadata_obj = _resolve_config(args)

        if not migrations_path.exists():
            self.console.print(
                "[yellow]Директория миграций не найдена.[/yellow]"
            )
            return

        cfg = _build_alembic_config(db_url, migrations_path)
        self.console.print("[cyan]История миграций:[/cyan]")
        command.history(cfg, verbose=True)
