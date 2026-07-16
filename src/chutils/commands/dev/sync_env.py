from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from .base import SubCommand


class SyncEnvSubCommand(SubCommand):
    """
    Подкоманда для синхронизации локального .env и его шаблона .env.example.
    """

    def register(self, subparsers: argparse._SubParsersAction[Any]) -> None:
        """Регистрирует подкоманду sync-env в argparse.

        Args:
            subparsers: Объект subparsers для добавления подкоманд.
        """
        sync_parser = subparsers.add_parser(
            "sync-env",
            help="Синхронизировать .env и .env.example",
            description="Синхронизирует переменные окружения между локальным .env и шаблоном .env.example.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""Примеры использования:
  chutils dev sync-env --dry-run
  chutils dev sync-env --yes
  chutils dev sync-env --env-path .env.dev --example-path .env.dev.example
""",
        )
        sync_parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Показать расхождения без физического изменения файлов",
        )
        sync_parser.add_argument(
            "-y",
            "--yes",
            "--force",
            dest="force",
            action="store_true",
            help="Применить изменения автоматически без интерактивного подтверждения",
        )
        sync_parser.add_argument(
            "--env-path",
            help="Путь к файлу .env (по умолчанию: .env)",
        )
        sync_parser.add_argument(
            "--example-path",
            help="Путь к файлу .env.example (по умолчанию: .env.example)",
        )
        sync_parser.set_defaults(handler=self.handle)

    def handle(self, args: argparse.Namespace) -> None:
        """Обработчик синхронизации env-файлов.

        Args:
            args: Объект Namespace с аргументами командной строки.
        """
        # Загружаем конфигурацию для получения путей к файлам
        from chutils.config.dev import load_ai_lint_config
        config = load_ai_lint_config()

        env_path = args.env_path or str(config.get("env_path", ".env"))
        example_path = args.example_path or str(config.get("example_path", ".env.example"))

        from chutils.env import is_rich_enabled
        from chutils.dev.env_sync import check_env_sync, sync_env_files

        env_path_obj = Path(env_path)
        example_path_obj = Path(example_path)

        self.console.print(
            f"Сравнение [cyan]{env_path_obj.name}[/cyan] и "
            f"[cyan]{example_path_obj.name}[/cyan]..."
        )

        try:
            diff = check_env_sync(env_path_obj, example_path_obj)
        except Exception as e:
            self.console.print(f"[bold red]Ошибка при чтении файлов:[/bold red] {e}")
            raise SystemExit(1)

        if not diff.has_diff():
            self.console.print(
                "[bold green]✓ Файлы полностью синхронизированы.[/bold green]"
            )
            return

        use_rich = is_rich_enabled()
        if use_rich:
            from rich.table import Table
            table = Table(title="Обнаруженные расхождения в переменных окружения")
            table.add_column("Файл", style="cyan")
            table.add_column("Переменная", style="magenta")
            table.add_column("Действие (при синхронизации)", style="green")

            for k in diff.missing_in_example:
                table.add_row(
                    example_path_obj.name,
                    k,
                    f"Добавить в {example_path_obj.name} (пустое значение)",
                )
            for k in diff.missing_in_env:
                table.add_row(
                    env_path_obj.name,
                    k,
                    f"Добавить в {env_path_obj.name} (дефолтное значение из {example_path_obj.name})",
                )

            self.console.print(table)
        else:
            self.console.print("\n=== Обнаруженные расхождения в переменных окружения ===")
            self.console.print(f"{'Файл':<20} | {'Переменная':<30} | Действие (при синхронизации)")
            self.console.print("-" * 80)
            for k in diff.missing_in_example:
                self.console.print(f"{example_path_obj.name:<20} | {k:<30} | Добавить в {example_path_obj.name} (пустое значение)")
            for k in diff.missing_in_env:
                self.console.print(f"{env_path_obj.name:<20} | {k:<30} | Добавить в {env_path_obj.name} (дефолтное значение из {example_path_obj.name})")
            self.console.print()

        if args.dry_run:
            self.console.print("[yellow]Dry-run режим. Изменения не внесены.[/yellow]")
            return

        sync_env = False
        sync_example = False

        if args.force:
            sync_env = bool(diff.missing_in_env)
            sync_example = bool(diff.missing_in_example)
        else:
            if use_rich:
                from rich.prompt import Confirm
                if diff.missing_in_env:
                    sync_env = Confirm.ask(
                        f"Добавить отсутствующие переменные в [cyan]{env_path_obj.name}[/cyan]?",
                        default=False,
                    )
                if diff.missing_in_example:
                    sync_example = Confirm.ask(
                        f"Добавить отсутствующие переменные в [cyan]{example_path_obj.name}[/cyan]?",
                        default=False,
                    )
            else:
                if diff.missing_in_env:
                    ans = input(f"Добавить отсутствующие переменные в {env_path_obj.name}? [y/N]: ").strip().lower()
                    sync_env = ans in ("y", "yes")
                if diff.missing_in_example:
                    ans = input(f"Добавить отсутствующие переменные в {example_path_obj.name}? [y/N]: ").strip().lower()
                    sync_example = ans in ("y", "yes")

        if not sync_env and not sync_example:
            self.console.print("[yellow]Синхронизация отменена пользователем.[/yellow]")
            return

        try:
            updated_env, updated_example = sync_env_files(
                env_path=env_path_obj,
                example_path=example_path_obj,
                sync_env=sync_env,
                sync_example=sync_example,
            )
            if updated_env:
                self.console.print(
                    f"[bold green]✓ Файл {env_path_obj.name} успешно обновлен.[/bold green]"
                )
            if updated_example:
                self.console.print(
                    f"[bold green]✓ Файл {example_path_obj.name} успешно обновлен.[/bold green]"
                )
        except Exception as e:
            self.console.print(
                f"[bold red]Ошибка при синхронизации файлов:[/bold red] {e}"
            )
            raise SystemExit(1)
