"""
Подкоманда CLI для профилирования времени импортов.
"""
from __future__ import annotations

import argparse
import sys
from typing import Any

from chutils.commands.dev.base import SubCommand


class ProfileImportsSubCommand(SubCommand):
    """
    Подкоманда dev profile-imports для анализа холодного старта и импортов модулей.
    """

    def register(self, subparsers: argparse._SubParsersAction[Any]) -> None:
        """Регистрирует подкоманду в argparse.

        Args:
            subparsers: Объект subparsers для добавления подкоманд.
        """
        # Аргументы уже зарегистрированы централизованно в DevCommand.register
        pass

    def handle(self, args: argparse.Namespace) -> None:
        """Обработчик выполнения профилирования.

        Args:
            args: Объект Namespace с аргументами командной строки.
        """
        # Бизнес-логику импортируем из chutils.dev.profile_imports
        from chutils.dev.profile_imports import profile_imports

        try:
            profile_imports(
                target=args.target,
                threshold_ms=args.threshold,
                as_table=args.table,
                as_json=args.json,
                console=self.console,
            )
        except Exception as e:
            self.err_console.print(f"[bold red]Ошибка при профилировании импортов:[/bold red] {e}")
            sys.exit(1)
        sys.exit(0)
