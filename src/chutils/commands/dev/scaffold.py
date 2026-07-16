from __future__ import annotations

import argparse
from typing import Any

from .base import SubCommand


class ScaffoldSubCommand(SubCommand):
    """
    Подкоманда для инициализации структуры нового модуля по принципам Чистой Архитектуры.
    """

    def register(self, subparsers: argparse._SubParsersAction[Any]) -> None:
        """Регистрирует подкоманду scaffold в argparse.

        Args:
            subparsers: Объект subparsers для добавления подкоманд.
        """
        scaffold_parser = subparsers.add_parser(
            "scaffold",
            help="Инициализировать новый модуль Чистой Архитектуры",
            description="Создает структуру каталогов и базовые классы/интерфейсы Чистой Архитектуры.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""Примеры использования:
  chutils dev scaffold my_module
  chutils dev scaffold my_module -o ./src/my_module -f
""",
        )
        scaffold_parser.add_argument(
            "module_name",
            help="Имя создаваемого модуля (валидный Python-идентификатор)",
        )
        scaffold_parser.add_argument(
            "-o",
            "--output-dir",
            help="Базовый путь для создания каталога модуля (по умолчанию: ./[module_name])",
        )
        scaffold_parser.add_argument(
            "-f",
            "--force",
            action="store_true",
            help="Принудительно перезаписать файлы, если целевая директория уже существует",
        )
        scaffold_parser.set_defaults(handler=self.handle)

    def handle(self, args: argparse.Namespace) -> None:
        """Обработчик генерации структуры модуля.

        Args:
            args: Объект Namespace с аргументами командной строки.
        """
        self.err_console.print(
            f"[bold yellow]Инициализация модуля Чистой Архитектуры '{args.module_name}'...[/bold yellow]"
        )
        from chutils.dev.scaffold import Scaffolder

        try:
            scaffolder = Scaffolder(
                module_name=args.module_name,
                output_dir=args.output_dir,
                force=args.force,
            )
            scaffolder.scaffold()
            self.console.print(
                f"[bold green] [OK] [/bold green] Модуль '{args.module_name}' успешно инициализирован."
            )
        except Exception as e:
            self.console.print(
                f"[bold red]Ошибка инициализации:[/bold red] {e}"
            )
            raise SystemExit(1)
