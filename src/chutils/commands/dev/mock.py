from __future__ import annotations

import argparse
from typing import Any

from .base import SubCommand


class MockSubCommand(SubCommand):
    """
    Подкоманда для запуска декларативного мок-сервера.
    """

    def register(self, subparsers: argparse._SubParsersAction[Any]) -> None:
        """Регистрирует подкоманду mock в argparse.

        Args:
            subparsers: Объект subparsers для добавления подкоманд.
        """
        mock_parser = subparsers.add_parser(
            "mock",
            help="Запустить декларативный мок-сервер",
            description="Запускает легковесный многопоточный мок-сервер на основе mocks.yml.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""Примеры использования:
  chutils dev mock
  chutils dev mock init
  chutils dev mock -p 9000 -r my_mocks.yml --proxy-fallback https://api.example.com
""",
        )
        mock_parser.add_argument(
            "-p",
            "--port",
            type=int,
            default=8888,
            help="Порт мок-сервера (по умолчанию: 8888)",
        )
        mock_parser.add_argument(
            "-r",
            "--routes",
            default="mocks.yml",
            help="Путь к конфигурационному файлу роутов (по умолчанию: mocks.yml)",
        )
        mock_parser.add_argument(
            "--proxy-fallback",
            help="Базовый URL для проксирования ненайденных запросов (Reverse Proxy)",
        )

        mock_subparsers = mock_parser.add_subparsers(
            dest="mock_subcommand", help="Действия мок-сервера"
        )
        init_parser = mock_subparsers.add_parser(
            "init",
            help="Инициализировать шаблонный файл конфигурации роутов (mocks.yml)",
        )
        init_parser.add_argument(
            "-o",
            "--output",
            default="mocks.yml",
            help="Путь для сохранения файла (по умолчанию: mocks.yml)",
        )

        mock_parser.set_defaults(handler=self.handle)

    def handle(self, args: argparse.Namespace) -> None:
        """Обработчик мок-сервера.

        Args:
            args: Объект Namespace с аргументами командной строки.
        """
        from chutils.dev.mock_server import MockServerRunner

        try:
            runner = MockServerRunner(
                port=args.port,
                routes_path=args.routes,
                proxy_fallback=args.proxy_fallback,
            )
            if getattr(args, "mock_subcommand", None) == "init":
                runner.init_template(getattr(args, "output", "mocks.yml"))
            else:
                runner.run()
        except Exception as e:
            self.console.print(
                f"[bold red]Ошибка мок-сервера:[/bold red] {e}"
            )
            raise SystemExit(1)
