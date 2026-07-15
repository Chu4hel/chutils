from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from .base import SubCommand


class DiagnosticsSubCommand(SubCommand):
    """
    Подкоманда для диагностики и проверки работоспособности среды (Health Check).
    """

    def register(self, subparsers: argparse._SubParsersAction[Any]) -> None:
        """Регистрирует подкоманду diagnostics в argparse.

        Args:
            subparsers: Объект subparsers для добавления подкоманд.
        """
        diagnostics_parser = subparsers.add_parser(
            "diagnostics",
            help="Запустить диагностику и проверку работоспособности среды (Health Check)",
            description="Выполняет встроенные и пользовательские проверки среды (keyring, конфигурация и др.) с выводом отчета.",
        )
        diagnostics_parser.add_argument(
            "--json",
            action="store_true",
            help="Вывести отчет в формате JSON",
        )
        diagnostics_parser.set_defaults(handler=self.handle)

    def handle(self, args: argparse.Namespace) -> None:
        """Обработчик диагностики и проверки работоспособности.

        Args:
            args: Объект Namespace с аргументами командной строки.
        """
        from chutils.diagnostics.manager import default_manager
        from chutils.env import is_rich_enabled

        report = default_manager.run_checks_sync()

        if args.json:
            print(json.dumps(report.model_dump(), indent=2, ensure_ascii=False))
            if report.status == "UNHEALTHY":
                sys.exit(1)
            sys.exit(0)

        if is_rich_enabled():
            from rich.table import Table

            status_colors = {
                "HEALTHY": "bold green",
                "DEGRADED": "bold yellow",
                "UNHEALTHY": "bold red"
            }
            status_color = status_colors.get(report.status, "white")

            self.console.print()
            self.console.print("[bold]Общий статус здоровья системы: [/bold]", end="")
            self.console.print(f"[{status_color}]{report.status}[/{status_color}]")
            self.console.print(f"Общее время выполнения: [cyan]{report.total_time:.4f}[/cyan] сек.")
            self.console.print()

            table = Table(title="Диагностические проверки", show_header=True, header_style="bold magenta")
            table.add_column("Название", style="cyan")
            table.add_column("Статус", justify="center")
            table.add_column("Критичность", justify="center")
            table.add_column("Время (сек)", justify="right", style="blue")
            table.add_column("Сообщение / Ошибка", style="yellow")

            for result in report.results:
                status_text = "[bold green]OK[/bold green]" if result.success else "[bold red]FAIL[/bold red]"
                critical_text = "[bold red]Критическая[/bold red]" if result.critical else "Некритическая"

                details = ""
                if result.error:
                    details = f"[red]Ошибка: {result.error}[/red]"
                elif result.message:
                    details = result.message

                table.add_row(
                    result.name,
                    status_text,
                    critical_text,
                    f"{result.execution_time:.4f}",
                    details
                )

            self.console.print(table)
        else:
            print()
            print(f"Общий статус здоровья системы: {report.status}")
            print(f"Общее время выполнения: {report.total_time:.4f} сек.")
            print()
            print(f"{'Название':<15} | {'Статус':<6} | {'Критичность':<12} | {'Время (с)':<10} | Детали")
            print("-" * 80)
            for result in report.results:
                status_text = "OK" if result.success else "FAIL"
                critical_text = "Да" if result.critical else "Нет"
                details = result.error if result.error else (result.message or "")
                print(
                    f"{result.name:<15} | {status_text:<6} | {critical_text:<12} | {result.execution_time:<10.4f} | {details}")

        if report.status == "UNHEALTHY":
            sys.exit(1)
        sys.exit(0)
