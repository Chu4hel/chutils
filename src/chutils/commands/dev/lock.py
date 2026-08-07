"""
Подкоманда CLI chutils dev lock для принудительной автоматической перегенерации всего ранее созданного контекста.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .base import SubCommand
from .generate_context import GenerateContextSubCommand


class LockSubCommand(SubCommand):
    """Подкоманда dev lock для повторной перегенерации контекста на основе реестра .chutils/context_metadata.json."""

    def register(self, subparsers: argparse._SubParsersAction[Any]) -> None:
        """Регистрирует подкоманду lock в argparse.

        Args:
            subparsers: Объект subparsers для добавления подкоманд.
        """
        lock_parser = subparsers.add_parser(
            "lock",
            help="Перегенерировать весь контекст проекта из реестра",
            description=(
                "Читает реестр .chutils/context_metadata.json и автоматически перегенерирует "
                "все зарегистрированные ранее файлы контекста (api_map.md, project_index.json и др.)."
            ),
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""Примеры использования:
  chutils dev lock
  chutils dev lock --force
""",
        )
        lock_parser.add_argument(
            "--force",
            action="store_true",
            help="Принудительно перезаписать все файлы, даже если содержимое не изменилось",
        )
        lock_parser.set_defaults(handler=self.handle)

    def handle(self, args: argparse.Namespace) -> None:
        """Обработчик выполнения подкоманды dev lock.

        Args:
            args: Объект Namespace с аргументами командной строки.
        """
        base_dir = Path.cwd()
        cache_path = base_dir / ".chutils" / "context_metadata.json"

        if not cache_path.exists():
            self.console.print(
                "[bold yellow][WARN] Реестр файлов контекста не найден (.chutils/context_metadata.json).[/bold yellow]"
            )
            self.console.print(
                "Сгенерируйте контекст командой: [cyan]chutils dev generate-context -o api_map.md[/cyan]")
            return

        try:
            with open(cache_path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            self.console.print(f"[bold red]Ошибка при чтении файла реестра {cache_path}: {e}[/bold red]")
            raise SystemExit(1)

        files_registry: dict[str, dict[str, Any]] = {}
        if isinstance(data, dict):
            if "files" in data and isinstance(data["files"], dict):
                files_registry = data["files"]
            elif "file_path" in data:
                old_fp = data.get("file_path", "")
                if old_fp:
                    files_registry[old_fp] = {
                        "format": str(data.get("format", "markdown")),
                        "target": "chutils",
                    }

        if not files_registry:
            self.console.print(
                "[bold yellow]Реестр контекста пуст. Зарегистрированные файлы отсутствуют.[/bold yellow]")
            return

        self.console.print(
            f"[bold cyan]Запуск синхронизации и перегенерации {len(files_registry)} файлов контекста...[/bold cyan]"
        )

        gen_subcommand = GenerateContextSubCommand()
        force_flag = bool(getattr(args, "force", False))

        for file_path, meta in files_registry.items():
            format_str = meta.get("format", "markdown")
            tree_flag = meta.get("tree", format_str == "tree")
            include_examples = meta.get("include_examples", False)
            ignore_list = meta.get("ignore", None)
            project_arg = meta.get("project_arg", None)
            target = meta.get("target", "chutils")

            # Если target был сохранен как "project" или передан project_arg, то используем project_arg
            if target == "project" and project_arg is None:
                project_arg = "."

            format_choice = "json" if format_str in ("json", "tree") else "markdown"

            gen_args = argparse.Namespace(
                format=format_choice,
                output=file_path,
                tree=tree_flag,
                no_weights=False,
                include_examples=include_examples,
                project=project_arg,
                ignore=ignore_list,
                gitignore=True,
                incremental=False,
                force=force_flag,
                untracked=False,
            )

            self.console.print(
                f"[bold yellow]Перегенерация ({target}):[/bold yellow] [cyan]{file_path}[/cyan] (format={format_str})"
            )
            try:
                gen_subcommand.handle(gen_args)
            except Exception as exc:
                self.console.print(f"[bold red]Ошибка при перегенерации {file_path}: {exc}[/bold red]")

        self.console.print("[bold green] [OK] Все файлы контекста проекта успешно перегенерированы![/bold green]")
