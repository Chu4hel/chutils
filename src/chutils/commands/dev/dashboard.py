"""
Подкоманда CLI для интерактивного TUI-дашборда CLI команд.
"""
from __future__ import annotations

import argparse
import sys
from typing import Any

from chutils.commands.dev.base import SubCommand


class DashboardSubCommand(SubCommand):
    """
    Подкоманда dev dashboard для интерактивного управления CLI-командами.
    """

    def register(self, subparsers: argparse._SubParsersAction[Any]) -> None:
        """Регистрирует подкоманду в argparse.

        Args:
            subparsers: Объект subparsers для добавления подкоманд.
        """
        # Аргументы уже зарегистрированы централизованно в DevCommand.register
        pass

    def handle(self, args: argparse.Namespace) -> None:
        """Обработчик выполнения подкоманды.

        Args:
            args: Объект Namespace с аргументами командной строки.
        """
        from chutils.dev.dashboard import run_dashboard

        try:
            run_dashboard(console=self.console)
        except Exception as e:
            self.err_console.print(f"[bold red]Ошибка при работе дашборда:[/bold red] {e}")
            sys.exit(1)
        sys.exit(0)
