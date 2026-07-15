from __future__ import annotations

import argparse
from typing import Any

from .base import SubCommand


class AiLintSubCommand(SubCommand):
    """
    Подкоманда для статического аудита AI-готовности кодовой базы.
    """

    def register(self, subparsers: argparse._SubParsersAction[Any]) -> None:
        """Регистрирует подкоманду ai-lint в argparse.

        Args:
            subparsers: Объект subparsers для добавления подкоманд.
        """
        lint_parser = subparsers.add_parser(
            "ai-lint",
            help="Проверить AI-готовность кодовой базы",
            description="Проверяет наличие манифестов ИИ (antigravity.md, agents.md, gemini.md), качество docstrings/type hints и отсутствие секретов.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""Примеры использования:
  chutils dev ai-lint
  chutils dev ai-lint --strict
  chutils dev ai-lint --ignore "temp/,build/"
""",
        )
        lint_parser.add_argument(
            "--strict",
            action="store_true",
            default=None,
            help="Строгий режим: считать предупреждения ошибками и завершаться с ошибкой.",
        )
        lint_parser.add_argument(
            "--soft-mode",
            action="store_true",
            default=None,
            help="Мягкий режим: выводить проблемы, но возвращать успешный статус (0).",
        )
        lint_parser.add_argument(
            "--ignore", help="Список исключаемых путей (через запятую)."
        )
        lint_parser.add_argument(
            "--rules",
            help="Список запускаемых правил через запятую (по умолчанию все).",
        )
        lint_parser.add_argument(
            "--custom-rules-path", help="Путь к файлу с пользовательскими правилами."
        )
        lint_parser.set_defaults(handler=self.handle)

    def handle(self, args: argparse.Namespace) -> None:
        """Обработчик проверки AI-готовности кодовой базы.

        Args:
            args: Объект Namespace с аргументами командной строки.
        """
        cli_args: dict[str, Any] = {}
        if args.strict is not None:
            cli_args["strict"] = args.strict
        if args.soft_mode is not None:
            cli_args["soft_mode"] = args.soft_mode
        if args.ignore:
            cli_args["ignore"] = [
                i.strip() for i in args.ignore.split(",") if i.strip()
            ]
        if args.rules:
            cli_args["rules"] = [r.strip() for r in args.rules.split(",") if r.strip()]
        if args.custom_rules_path:
            cli_args["custom_rules_path"] = args.custom_rules_path

        from chutils.config.dev import load_ai_lint_config
        from chutils.dev.ai_lint import LinterEngine

        try:
            config = load_ai_lint_config(cli_args=cli_args)
            engine = LinterEngine(config)

            self.err_console.print(
                "[bold yellow]Запуск аудита AI-готовности кодовой базы...[/bold yellow]"
            )
            results = engine.run()
            success = engine.print_results(results)

            if not success:
                raise SystemExit(1)
        except Exception as e:
            self.console.print(
                f"[bold red]Ошибка при выполнении ai-lint:[/bold red] {e}"
            )
            raise SystemExit(1)
