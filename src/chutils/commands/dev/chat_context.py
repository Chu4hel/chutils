from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from .base import SubCommand


class ChatContextSubCommand(SubCommand):
    """
    Подкоманда для сборки контекстного среза для ИИ-ассистента.
    """

    def register(self, subparsers: argparse._SubParsersAction[Any]) -> None:
        """Регистрирует подкоманду chat-context в argparse.

        Args:
            subparsers: Объект subparsers для добавления подкоманд.
        """
        chat_parser = subparsers.add_parser(
            "chat-context",
            help="Сгенерировать контекстный срез для ИИ-ассистента",
            description="Создает компактный Markdown-срез API, docstrings и examples для ИИ.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""Примеры использования:
  chutils dev chat-context -m logger,secret_manager
  chutils dev chat-context -t "logging and secrets" -l internal -o context.md
  chutils dev chat-context (интерактивный режим)
""",
        )
        chat_parser.add_argument(
            "-m",
            "--modules",
            help="Список модулей через запятую (например: logger,config).",
        )
        chat_parser.add_argument(
            "-t", "--task", help="Описание задачи или темы для автоподбора контекста."
        )
        chat_parser.add_argument(
            "-l",
            "--layer",
            choices=["public", "internal", "infrastructure", "private", "all"],
            default="public",
            help="Фильтр по слоям абстракции (по умолчанию: public)",
        )
        chat_parser.add_argument(
            "-o", "--output", help="Путь к файлу для сохранения результата."
        )
        chat_parser.set_defaults(handler=self.handle)

    def handle(self, args: argparse.Namespace) -> None:
        """Обработчик интерактивной сборки контекста.

        Args:
            args: Объект Namespace с аргументами командной строки.
        """
        from chutils.dev.chat_context import collect_context_slice, run_interactive_menu

        modules_list = None
        if args.modules:
            modules_list = [m.strip() for m in args.modules.split(",") if m.strip()]

        project_path = Path(".").resolve()

        # Если не указаны ни модули, ни задача, запускаем интерактивный режим
        if not modules_list and not args.task:
            modules_list = run_interactive_menu(project_path)
            if not modules_list:
                return

        self.err_console.print(
            "[bold yellow]Сборка контекстного среза...[/bold yellow]"
        )

        try:
            markdown_content = collect_context_slice(
                project_path=project_path,
                modules=modules_list,
                task=args.task,
                layer=args.layer,
            )

            if args.output:
                output_path = Path(args.output).resolve()
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text(markdown_content, encoding="utf-8")
                self.console.print(
                    f"[bold green] [OK] [/bold green] Контекстный срез успешно сохранен в: [cyan]{args.output}[/cyan]"
                )
            else:
                # В stdout выводим сгенерированный Markdown
                print(markdown_content)

        except Exception as e:
            self.console.print(
                f"[bold red]Ошибка при генерации контекста:[/bold red] {e}"
            )
            raise SystemExit(1)
