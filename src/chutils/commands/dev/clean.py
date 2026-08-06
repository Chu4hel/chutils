"""
Подкоманда CLI для очистки проекта от временных файлов и кэшей (chutils dev clean).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from chutils.commands.dev.base import SubCommand
from chutils.dev.cleaner import CleanItem, execute_clean, scan_project


class CleanSubCommand(SubCommand):
    """Подкоманда dev clean для удаления временных файлов и кэшей разработки."""

    def register(self, subparsers: argparse._SubParsersAction[Any]) -> None:
        """Регистрирует подкоманду в argparse (регистрация делается в DevCommand).

        Args:
            subparsers: Действие подпарсеров argparse.
        """
        pass

    def handle(self, args: argparse.Namespace) -> None:
        """Обработчик выполнения подкоманды dev clean.

        Args:
            args: Объект Namespace с аргументами командной строки.
        """
        cli_args = {
            "exclude": getattr(args, "exclude", None),
            "include": getattr(args, "include", None),
            "dry_run": getattr(args, "dry_run", False),
            "force": getattr(args, "force", False),
        }

        # Сканируем проект
        base_dir = Path.cwd()
        items: list[CleanItem] = scan_project(base_dir=base_dir, extra_targets=None)

        if not items:
            self.console.print("[bold green]Мусорные файлы не обнаружены. Проект чист![/bold green]")
            sys.exit(0)

        total_bytes = sum(item.size_bytes for item in items)
        formatted_total = self._format_size(total_bytes)

        self.console.print(
            f"\n[bold yellow]Обнаружено элементов для очистки:[/bold yellow] {len(items)} "
            f"([bold cyan]всего {formatted_total}[/bold cyan])\n"
        )

        # Вывод таблицы с элементами
        self._print_items_table(items)

        # Режим имитации (--dry-run)
        if cli_args["dry_run"]:
            self.console.print(
                "\n[bold blue][DRY-RUN][/bold blue] Режим имитации завершен. "
                f"Ни один файл не был удален. Освобождаемый объем: [bold cyan]{formatted_total}[/bold cyan]."
            )
            sys.exit(0)

        # Интерактивное подтверждение, если не передан --yes / --force
        if not cli_args["force"]:
            try:
                answer = input(
                    f"\nВы действительно хотите удалить эти элементы ({formatted_total})? [y/N]: "
                ).strip().lower()
            except (KeyboardInterrupt, EOFError):
                self.console.print("\n[yellow]Операция очистки отменена пользователем.[/yellow]")
                sys.exit(0)

            if answer not in ("y", "yes", "д", "да"):
                self.console.print("[yellow]Операция очистки отменена.[/yellow]")
                sys.exit(0)

        # Выполнение фактической очистки
        removed_count, freed_bytes = execute_clean(items)
        freed_formatted = self._format_size(freed_bytes)

        self.console.print(
            f"\n[bold green]Уборка завершена![/bold green] "
            f"Удалено элементов: [bold white]{removed_count}/{len(items)}[/bold white], "
            f"освобождено места: [bold cyan]{freed_formatted}[/bold cyan]."
        )
        sys.exit(0)

    def _format_size(self, size_bytes: int) -> str:
        size = float(size_bytes)
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024.0:
                return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
            size /= 1024.0
        return f"{size:.1f} TB"

    def _print_items_table(self, items: list[CleanItem]) -> None:
        """Отображает список элементов для очистки с использованием rich или базовой консоли."""
        try:
            from rich.table import Table

            table = Table(title="Элементы для удаления", show_header=True, header_style="bold magenta")
            table.add_column("№", justify="right", style="dim", width=4)
            table.add_column("Тип", justify="center", width=8)
            table.add_column("Путь", justify="left")
            table.add_column("Размер", justify="right", style="cyan", width=12)

            for idx, item in enumerate(items, start=1):
                item_type = "[bold blue]DIR[/bold blue]" if item.is_dir else "[green]FILE[/green]"
                try:
                    rel_path = item.path.relative_to(Path.cwd())
                except ValueError:
                    rel_path = item.path
                table.add_row(str(idx), item_type, str(rel_path), item.display_size)

            self.console.print(table)
        except Exception:
            # Fallback текстовый вывод
            self.console.print("Список элементов для удаления:")
            for idx, item in enumerate(items, start=1):
                item_type = "DIR " if item.is_dir else "FILE"
                try:
                    rel_path = item.path.relative_to(Path.cwd())
                except ValueError:
                    rel_path = item.path
                self.console.print(f" {idx:3d}. [{item_type}] {rel_path} ({item.display_size})")
