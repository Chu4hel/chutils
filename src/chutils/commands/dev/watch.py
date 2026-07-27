"""
Подкоманда CLI для Live Dev режима с hot-reload (chutils dev watch).
"""

from __future__ import annotations

import argparse
import sys
import time
from typing import Any

from ...dev.runners import BaseRunner, InProcessReloader, SubprocessRunner
from ...dev.watcher import get_watcher
from .base import SubCommand


class WatchSubCommand(SubCommand):
    """Подкоманда dev watch для автоматического перезапуска приложений при изменении файлов."""

    def register(self, subparsers: argparse._SubParsersAction[Any]) -> None:
        """
        Регистрирует подкоманду в argparse.

        Args:
            subparsers: Объект subparsers для добавления подкоманд.
        """

    def handle(self, args: argparse.Namespace) -> None:
        """
        Обработчик выполнения подкоманды dev watch.

        Args:
            args: Объект Namespace с аргументами командной строки.
        """
        paths: list[str] = getattr(args, "paths", None) or ["."]
        ext_arg: str | None = getattr(args, "extensions", None)
        extensions: list[str] | None = [e.strip() for e in ext_arg.split(",")] if ext_arg else None

        ignore_arg: str | None = getattr(args, "ignore", None)
        ignore_patterns: list[str] | None = [i.strip() for i in ignore_arg.split(",")] if ignore_arg else None

        debounce: float = getattr(args, "debounce", 0.5)
        module_target: str | None = getattr(args, "module", None)
        raw_cmd: list[str] | None = getattr(args, "command", None)

        runner: BaseRunner
        if module_target:
            try:
                runner = InProcessReloader(target=module_target)
            except ValueError as err:
                self.err_console.print(f"[bold red]Ошибка аргументов:[/bold red] {err}")
                sys.exit(1)
        elif raw_cmd:
            cmd_list = list(raw_cmd)
            if cmd_list and cmd_list[0] == "--":
                cmd_list.pop(0)

            if not cmd_list:
                self.err_console.print(
                    "[bold red]Ошибка:[/bold red] Команда для выполнения пуста. "
                    "Использование: chutils dev watch -- <command>"
                )
                sys.exit(1)

            runner = SubprocessRunner(command=cmd_list)
        else:
            self.err_console.print(
                "[bold red]Ошибка:[/bold red] Укажите команду для выполнения после '--' или модуль через '-m module:func'.\n"
                "Примеры:\n"
                "  chutils dev watch -- python main.py\n"
                "  chutils dev watch -m myapp.main:start"
            )
            sys.exit(1)

        runner.start()

        def on_change(changed_files: list[str]) -> None:
            self.console.print(
                f"[bold yellow][watch][/bold yellow] Обнаружены изменения в {len(changed_files)} файлах. Перезапуск..."
            )
            runner.restart()

        watcher = get_watcher(
            paths=paths,
            extensions=extensions,
            ignore_patterns=ignore_patterns,
            debounce_seconds=debounce,
            callback=on_change,
        )

        watcher.start()
        self.console.print(
            f"[bold green][watch] Live Dev режим запущен.[/bold green] Отслеживаем: {paths}. "
            "Нажмите Ctrl+C для выхода."
        )

        try:
            while watcher.is_running:
                time.sleep(0.2)
        except KeyboardInterrupt:
            self.console.print("\n[bold cyan][watch] Остановка отслеживания...[/bold cyan]")
        finally:
            watcher.stop()
            runner.stop()
            self.console.print("[bold green][watch] Отслеживание успешно завершено.[/bold green]")
