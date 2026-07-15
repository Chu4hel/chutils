from __future__ import annotations

import argparse
from typing import Any

from .base import BaseCommand


class PyPiCommand(BaseCommand):
    """
    Проверка доступности и производительности зеркал PyPI.
    
    Позволяет измерять время отклика и скорость загрузки пакетов
    с официального PyPI и различных зеркал.
    """

    def register(self, subparsers: argparse._SubParsersAction[Any]) -> None:
        """Регистрирует команду pypi и её подкоманды в argparse.

        Args:
            subparsers: Объект subparsers для добавления подкоманд.
        """
        # Создаем общий парсер для аргументов проверки, чтобы избежать дублирования
        check_args_parser = argparse.ArgumentParser(add_help=False)
        check_args_parser.add_argument(
            "-m", "--mirrors",
            help="Кастомные зеркала для проверки (список URL через запятую)"
        )
        check_args_parser.add_argument(
            "--json",
            action="store_true",
            help="Вывод результатов в формате JSON"
        )
        check_args_parser.add_argument(
            "--package",
            default="six",
            help="Имя пакета для теста скорости загрузки (по умолчанию: six)"
        )

        pypi_parser = subparsers.add_parser(
            "pypi",
            parents=[check_args_parser],
            help="Проверка доступа к PyPI и зеркалам",
            description="Команды для проверки доступности и производительности репозиториев PyPI.",
        )
        pypi_parser.set_defaults(handler=self.handle)

        pypi_subparsers = pypi_parser.add_subparsers(
            dest="subcommand", help="Доступные действия"
        )

        # pypi check
        pypi_subparsers.add_parser(
            "check",
            parents=[check_args_parser],
            help="Проверка доступности и скорости зеркал PyPI",
            description="Измеряет время отклика и скорость загрузки с зеркал PyPI.",
        )

    def handle(self, args: argparse.Namespace) -> None:
        """Обработчик команды pypi.

        Args:
            args: Объект Namespace с аргументами командной строки.
        """
        # Если subcommand не указан или равен check (поведение по умолчанию)
        if not args.subcommand or args.subcommand == "check":
            self.handle_check(args)
        else:
            # Выводим помощь
            parser = argparse.ArgumentParser()
            subparsers = parser.add_subparsers()
            self.register(subparsers)
            parser.parse_args(["pypi", "--help"])

    def handle_check(self, args: argparse.Namespace) -> None:
        """Выполняет проверку доступности и скорости зеркал PyPI.

        Args:
            args: Объект Namespace с аргументами.
        """
        self.console.print("[INFO] Проверка зеркал PyPI начата...")
