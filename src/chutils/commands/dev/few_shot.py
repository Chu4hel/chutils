from __future__ import annotations

import argparse
from typing import Any

from .base import SubCommand


class FewShotSubCommand(SubCommand):
    """
    Подкоманда для автоматической генерации банка few-shot примеров.
    """

    def register(self, subparsers: argparse._SubParsersAction[Any]) -> None:
        """Регистрирует подкоманду generate-few-shot в argparse.

        Args:
            subparsers: Объект subparsers для добавления подкоманд.
        """
        few_shot_parser = subparsers.add_parser(
            "generate-few-shot",
            help="Автогенерация few-shot примеров для целевого проекта",
            description="Анализирует проект, детектирует архитектурные абстракции и создает банк few-shot примеров в docs/ai_examples/.",
        )
        few_shot_parser.add_argument(
            "-p",
            "--project",
            required=True,
            help="Путь к корневой директории целевого проекта.",
        )
        few_shot_parser.add_argument(
            "-f",
            "--force",
            action="store_true",
            help="Принудительно перезаписать файлы при совпадении имен существующих категорий.",
        )
        few_shot_parser.set_defaults(handler=self.handle)

    def handle(self, args: argparse.Namespace) -> None:
        """Обработчик автогенерации few-shot примеров.

        Args:
            args: Объект Namespace с аргументами командной строки.
        """
        from chutils.dev.few_shot import generate_few_shot_bank

        try:
            generate_few_shot_bank(
                project_path=args.project,
                force=args.force,
                console=self.console,
            )
        except Exception as e:
            self.console.print(f"[bold red]Ошибка генерации few-shot банка:[/bold red] {e}")
            raise SystemExit(1)
