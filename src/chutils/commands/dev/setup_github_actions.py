from __future__ import annotations

import argparse
import os
from typing import Any

from chutils.dev.github_actions import generate_workflow_yaml
from .base import SubCommand


class SetupGithubActionsSubCommand(SubCommand):
    """
    Подкоманда для интерактивной настройки и генерации GitHub Actions.
    """

    def register(self, subparsers: argparse._SubParsersAction[Any]) -> None:
        """Регистрирует подкоманду setup-github-actions в argparse.

        Args:
            subparsers: Объект subparsers для добавления подкоманд.
        """
        parser = subparsers.add_parser(
            "setup-github-actions",
            help="Интерактивная настройка и генерация GitHub Actions",
            description="Генерирует и настраивает workflow для GitHub Actions на основе setup-uv.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )

        interactive_group = parser.add_mutually_exclusive_group()
        interactive_group.add_argument(
            "--interactive",
            action="store_true",
            dest="interactive",
            default=True,
            help="Запустить интерактивную настройку (по умолчанию)"
        )
        interactive_group.add_argument(
            "--no-interactive",
            action="store_false",
            dest="interactive",
            help="Отключить интерактивный опрос"
        )

        parser.add_argument(
            "--python-versions",
            default="3.10,3.11,3.12,3.13",
            help="Список версий Python через запятую (например, 3.10,3.11,3.12,3.13)"
        )

        pytest_group = parser.add_mutually_exclusive_group()
        pytest_group.add_argument("--with-pytest", action="store_true", dest="with_pytest", default=None)
        pytest_group.add_argument("--without-pytest", action="store_false", dest="with_pytest", default=None)

        mypy_group = parser.add_mutually_exclusive_group()
        mypy_group.add_argument("--with-mypy", action="store_true", dest="with_mypy", default=None)
        mypy_group.add_argument("--without-mypy", action="store_false", dest="with_mypy", default=None)

        ruff_group = parser.add_mutually_exclusive_group()
        ruff_group.add_argument("--with-ruff", action="store_true", dest="with_ruff", default=None)
        ruff_group.add_argument("--without-ruff", action="store_false", dest="with_ruff", default=None)

        ailint_group = parser.add_mutually_exclusive_group()
        ailint_group.add_argument("--with-ai-lint", action="store_true", dest="with_ai_lint", default=None)
        ailint_group.add_argument("--without-ai-lint", action="store_false", dest="with_ai_lint", default=None)

        parser.add_argument(
            "--output-file",
            default=".github/workflows/ci.yml",
            help="Путь для сохранения сгенерированного workflow (по умолчанию: .github/workflows/ci.yml)"
        )

        parser.set_defaults(handler=self.handle)

    def handle(self, args: argparse.Namespace) -> None:
        """Выполняет генерацию и настройку GitHub Actions workflow.

        Args:
            args: Объект Namespace с аргументами командной строки.
        """
        python_versions_str = args.python_versions
        with_pytest = args.with_pytest
        with_mypy = args.with_mypy
        with_ruff = args.with_ruff
        with_ai_lint = args.with_ai_lint
        output_file = args.output_file

        if args.interactive:
            self.console.print("[bold cyan]Настройка GitHub Actions CI[/bold cyan]")
            self.console.print(
                "Пожалуйста, ответьте на следующие вопросы (оставьте пустым для значений по умолчанию):\n")

            try:
                python_versions_str = self._ask_str("Версии Python (через запятую)", python_versions_str)
                with_pytest = self._ask_yes_no("Запускать тесты с pytest?",
                                               with_pytest if with_pytest is not None else True)
                with_ruff = self._ask_yes_no("Запускать линтер ruff?", with_ruff if with_ruff is not None else True)
                with_mypy = self._ask_yes_no("Запускать статический анализ mypy?",
                                             with_mypy if with_mypy is not None else True)
                with_ai_lint = self._ask_yes_no("Запускать аудит AI-готовности chutils dev ai-lint?",
                                                with_ai_lint if with_ai_lint is not None else True)
                output_file = self._ask_str("Путь для сохранения workflow", output_file)
            except (KeyboardInterrupt, EOFError):
                self.console.print("\n[yellow]Настройка отменена пользователем.[/yellow]")
                raise SystemExit(1)

        # Разрешаем неопределенные значения
        python_versions = [v.strip() for v in python_versions_str.split(",") if v.strip()]
        if not python_versions:
            self.err_console.print("[bold red]Ошибка:[/bold red] Необходимо указать хотя бы одну версию Python.")
            raise SystemExit(1)

        final_with_pytest = with_pytest if with_pytest is not None else True
        final_with_mypy = with_mypy if with_mypy is not None else True
        final_with_ruff = with_ruff if with_ruff is not None else True
        final_with_ai_lint = with_ai_lint if with_ai_lint is not None else True

        yaml_content = generate_workflow_yaml(
            python_versions=python_versions,
            with_pytest=final_with_pytest,
            with_mypy=final_with_mypy,
            with_ruff=final_with_ruff,
            with_ai_lint=final_with_ai_lint,
        )

        try:
            dir_path = os.path.dirname(output_file)
            if dir_path:
                os.makedirs(dir_path, exist_ok=True)
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(yaml_content)
            self.console.print(f"[green]Workflow успешно сохранен в {output_file}[/green]")
        except Exception as e:
            self.err_console.print(f"[bold red]Ошибка при сохранении файла:[/bold red] {e}")
            raise SystemExit(1)

    def _ask_str(self, prompt: str, default: str) -> str:
        """Спрашивает у пользователя строку."""
        val = input(f"{prompt} [{default}]: ").strip()
        return val if val else default

    def _ask_yes_no(self, prompt: str, default: bool) -> bool:
        """Спрашивает у пользователя булево значение."""
        default_str = "Y/n" if default else "y/N"
        val = input(f"{prompt} [{default_str}]: ").strip().lower()
        if not val:
            return default
        return val in ("y", "yes", "true", "1")
