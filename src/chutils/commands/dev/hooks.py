from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from .base import SubCommand


class HooksSubCommand(SubCommand):
    """
    Подкоманда для установки pre-commit Git-хука проверки ai-lint.
    """

    def register(self, subparsers: argparse._SubParsersAction[Any]) -> None:
        """Регистрирует подкоманду install-hooks в argparse.

        Args:
            subparsers: Объект subparsers для добавления подкоманд.
        """
        hooks_parser = subparsers.add_parser(
            "install-hooks",
            help="Установить pre-commit Git-хук для проверки ai-lint",
            description="Создает или обновляет pre-commit хук в .git/hooks для автоматического запуска ai-lint перед коммитами.",
        )
        hooks_parser.add_argument(
            "-f",
            "--force",
            action="store_true",
            help="Принудительно перезаписать существующий pre-commit хук.",
        )
        hooks_parser.add_argument(
            "--ruff",
            action="store_true",
            help="Добавить автоматическую проверку ruff check/format в pre-commit хук.",
        )
        hooks_parser.add_argument(
            "--flake8",
            action="store_true",
            help="Добавить проверку стиля flake8 в pre-commit хук.",
        )
        hooks_parser.set_defaults(handler=self.handle)

    def handle(self, args: argparse.Namespace) -> None:
        """Установка pre-commit хука.

        Args:
            args: Объект Namespace с аргументами командной строки.
        """
        import os
        from chutils.exceptions import ChutilsException

        current = Path(os.getcwd()).resolve()
        git_dir = None
        for parent in [current] + list(current.parents):
            potential_git = parent / ".git"
            if potential_git.exists() and potential_git.is_dir():
                git_dir = potential_git
                break

        if not git_dir:
            raise ChutilsException(
                "Директория '.git' не найдена. Убедитесь, что проект является Git-репозиторием "
                "и вы находитесь внутри него.",
                hint="Выполните 'git init', чтобы инициализировать репозиторий."
            )

        hooks_dir = git_dir / "hooks"
        from chutils.fs import ensure_dir
        ensure_dir(hooks_dir)
        hook_path = hooks_dir / "pre-commit"

        # Подготовка вспомогательных вызовов ruff/flake8
        extra_checks = ""
        if getattr(args, "ruff", False):
            extra_checks += (
                "# Запуск ruff check & format\n"
                "if [ -f uv.lock ] && command -v uv >/dev/null 2>&1; then\n"
                "    uv run ruff check --fix && uv run ruff format\n"
                "elif [ -f poetry.lock ] && command -v poetry >/dev/null 2>&1; then\n"
                "    poetry run ruff check --fix && poetry run ruff format\n"
                "elif command -v ruff >/dev/null 2>&1; then\n"
                "    ruff check --fix && ruff format\n"
                "fi\n\n"
            )
        if getattr(args, "flake8", False):
            extra_checks += (
                "# Запуск flake8\n"
                "if [ -f uv.lock ] && command -v uv >/dev/null 2>&1; then\n"
                "    uv run flake8 .\n"
                "elif [ -f poetry.lock ] && command -v poetry >/dev/null 2>&1; then\n"
                "    poetry run flake8 .\n"
                "elif command -v flake8 >/dev/null 2>&1; then\n"
                "    flake8 .\n"
                "fi\n\n"
            )

        hook_template = (
            "#!/bin/sh\n"
            "# chutils pre-commit hook\n"
            "# === CHUTILS HOOK START ===\n"
            f"{extra_checks}"
            "# Автоматическое определение окружения и запуск ai-lint\n"
            "if [ -f uv.lock ] && command -v uv >/dev/null 2>&1; then\n"
            "    uv run chutils dev ai-lint --staged\n"
            "elif [ -f poetry.lock ] && command -v poetry >/dev/null 2>&1; then\n"
            "    poetry run chutils dev ai-lint --staged\n"
            "elif [ -f Pipfile ] && command -v pipenv >/dev/null 2>&1; then\n"
            "    pipenv run chutils dev ai-lint --staged\n"
            "elif [ -d .venv ]; then\n"
            "    .venv/bin/chutils dev ai-lint --staged || .venv/Scripts/chutils dev ai-lint --staged || .venv/bin/python -m chutils dev ai-lint --staged || .venv/Scripts/python -m chutils dev ai-lint --staged\n"
            "elif [ -d venv ]; then\n"
            "    venv/bin/chutils dev ai-lint --staged || venv/Scripts/chutils dev ai-lint --staged || venv/bin/python -m chutils dev ai-lint --staged || venv/Scripts/python -m chutils dev ai-lint --staged\n"
            "elif command -v uv >/dev/null 2>&1; then\n"
            "    uv run chutils dev ai-lint --staged\n"
            "elif command -v poetry >/dev/null 2>&1; then\n"
            "    poetry run chutils dev ai-lint --staged\n"
            "elif command -v chutils >/dev/null 2>&1; then\n"
            "    chutils dev ai-lint --staged\n"
            "else\n"
            "    python3 -m chutils dev ai-lint --staged || python -m chutils dev ai-lint --staged\n"
            "fi\n"
            "# === CHUTILS HOOK END ===\n"
        )

        if not hook_path.exists() or args.force:
            try:
                with open(hook_path, "w", encoding="utf-8", newline="\n") as f:
                    f.write(hook_template)
            except Exception as e:
                raise ChutilsException(f"Не удалось записать файл хука: {e}")
            self.console.print("[bold green]✓ Git-хук pre-commit успешно установлен![/bold green]")
        else:
            try:
                with open(hook_path, "r", encoding="utf-8", errors="ignore") as f:
                    existing_content = f.read()
            except Exception as e:
                raise ChutilsException(f"Не удалось прочитать существующий файл хука: {e}")

            if "# chutils pre-commit hook" in existing_content:
                self.console.print("[yellow]⚠ Git-хук chutils уже установлен в файле pre-commit.[/yellow]")
            else:
                try:
                    separator = "" if existing_content.endswith("\n") else "\n"
                    block = (
                        f"{separator}"
                        "# === CHUTILS HOOK START ===\n"
                        "# chutils pre-commit hook\n"
                        f"{extra_checks}"
                        "# Автоматическое определение окружения и запуск ai-lint\n"
                        "if [ -f uv.lock ] && command -v uv >/dev/null 2>&1; then\n"
                        "    uv run chutils dev ai-lint --staged\n"
                        "elif [ -f poetry.lock ] && command -v poetry >/dev/null 2>&1; then\n"
                        "    poetry run chutils dev ai-lint --staged\n"
                        "elif [ -f Pipfile ] && command -v pipenv >/dev/null 2>&1; then\n"
                        "    pipenv run chutils dev ai-lint --staged\n"
                        "elif [ -d .venv ]; then\n"
                        "    .venv/bin/chutils dev ai-lint --staged || .venv/Scripts/chutils dev ai-lint --staged || .venv/bin/python -m chutils dev ai-lint --staged || .venv/Scripts/python -m chutils dev ai-lint --staged\n"
                        "elif [ -d venv ]; then\n"
                        "    venv/bin/chutils dev ai-lint --staged || venv/Scripts/chutils dev ai-lint --staged || venv/bin/python -m chutils dev ai-lint --staged || venv/Scripts/python -m chutils dev ai-lint --staged\n"
                        "elif command -v uv >/dev/null 2>&1; then\n"
                        "    uv run chutils dev ai-lint --staged\n"
                        "elif command -v poetry >/dev/null 2>&1; then\n"
                        "    poetry run chutils dev ai-lint --staged\n"
                        "elif command -v chutils >/dev/null 2>&1; then\n"
                        "    chutils dev ai-lint --staged\n"
                        "else\n"
                        "    python3 -m chutils dev ai-lint --staged || python -m chutils dev ai-lint --staged\n"
                        "fi\n"
                        "# === CHUTILS HOOK END ===\n"
                    )
                    with open(hook_path, "a", encoding="utf-8", newline="\n") as f:
                        f.write(block)
                except Exception as e:
                    raise ChutilsException(f"Не удалось дописать в файл хука: {e}")
                self.console.print(
                    "[bold green]✓ Блок проверки chutils добавлен в существующий pre-commit хук![/bold green]")

        if sys.platform != "win32":
            try:
                current_mode = hook_path.stat().st_mode
                hook_path.chmod(current_mode | 0o111 | 0o444)
            except Exception as e:
                self.console.print(f"[yellow]⚠ Не удалось установить права chmod +x для хука: {e}[/yellow]")
