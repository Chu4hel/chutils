"""
Модуль для сканирования и извлечения CLI-команд, декорированных @cli_command.
"""
from __future__ import annotations

import ast
import os
import re
from pathlib import Path
from typing import NamedTuple


class CLIArgument(NamedTuple):
    """Информация об аргументе CLI-команды."""
    name: str
    type_str: str
    default_str: str | None
    help_text: str | None


class CLICommandInfo:
    """Информация об обнаруженной CLI-команде."""

    name: str
    file_path: str
    docstring: str | None
    arguments: list[CLIArgument]

    def __init__(
            self,
            name: str,
            file_path: str,
            docstring: str | None,
            arguments: list[CLIArgument],
    ) -> None:
        """Инициализирует информацию о CLI-команде.

        Args:
            name: Имя функции/команды.
            file_path: Путь к файлу с командой.
            docstring: Докстринг функции.
            arguments: Список аргументов.
        """
        self.name = name
        self.file_path = file_path
        self.docstring = docstring
        self.arguments = arguments


def parse_docstring_args(docstring: str | None) -> dict[str, str]:
    """Парсит docstring в стиле Google для извлечения описаний аргументов.

    Args:
        docstring: Текст docstring.

    Returns:
        Словарь {имя_аргумента: описание}.
    """
    if not docstring:
        return {}

    arg_help = {}
    # Регулярка для поиска секции Args
    args_section = re.search(r"Args:\s*(.*?)(\n\n|\n[A-Z]|$)", docstring, re.DOTALL)
    if args_section:
        content = args_section.group(1)
        # Регулярка для поиска отдельных аргументов: "name (type): description"
        matches = re.findall(r"^\s*([a-zA-Z_0-9]+)\s*(\(.*?\))?:\s*(.*?)$", content, re.MULTILINE)
        for name, _, desc in matches:
            arg_help[name] = desc.strip()

    return arg_help


class CLICommandDiscoverer:
    """Поиск и парсинг функций с декоратором @cli_command."""

    def __init__(self, root_dir: str | Path) -> None:
        """Инициализирует CLICommandDiscoverer.

        Args:
            root_dir: Корневой каталог для поиска.
        """
        self.root_dir = Path(root_dir).resolve()

    def discover(self) -> list[CLICommandInfo]:
        """Ищет и парсит все файлы .py в корневом каталоге.

        Returns:
            Список найденных команд CLI.
        """
        commands: list[CLICommandInfo] = []

        ignore_dirs = {
            ".git",
            ".venv",
            "venv",
            "__pycache__",
            "build",
            "dist",
            ".pytest_cache",
            ".mypy_cache",
        }

        for root, dirs, files in os.walk(self.root_dir):
            # Фильтруем папки на месте
            dirs[:] = [d for d in dirs if d not in ignore_dirs and not d.startswith(".")]

            for file in files:
                if file.endswith(".py"):
                    file_path = Path(root) / file
                    try:
                        commands.extend(self._parse_file(file_path))
                    except Exception:
                        # Игнорируем ошибки парсинга некорректных/битых файлов
                        continue

        return sorted(commands, key=lambda x: x.name)

    def _parse_file(self, file_path: Path) -> list[CLICommandInfo]:
        """Парсит один файл Python на наличие @cli_command.

        Args:
            file_path: Путь к файлу.

        Returns:
            Список обнаруженных команд в файле.
        """
        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception:
            return []

        if "cli_command" not in content:
            return []

        try:
            tree = ast.parse(content, filename=str(file_path))
        except SyntaxError:
            return []

        commands: list[CLICommandInfo] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                if self._has_cli_decorator(node):
                    commands.append(self._extract_command_info(node, file_path))

        return commands

    def _has_cli_decorator(self, node: ast.FunctionDef) -> bool:
        """Проверяет, есть ли у функции декоратор cli_command."""
        for dec in node.decorator_list:
            # Случай: @cli_command
            if isinstance(dec, ast.Name) and dec.id == "cli_command":
                return True
            # Случай: @cli_command() или с аргументами
            elif isinstance(dec, ast.Call) and isinstance(dec.func, ast.Name) and dec.func.id == "cli_command":
                return True
            # Случай: @chutils.cli_command
            elif isinstance(dec, ast.Attribute) and dec.attr == "cli_command":
                return True
        return False

    def _extract_command_info(self, node: ast.FunctionDef, file_path: Path) -> CLICommandInfo:
        """Извлекает информацию о CLI-команде из AST-узла функции.

        Args:
            node: Узел функции.
            file_path: Путь к файлу.

        Returns:
            Объект CLICommandInfo.
        """
        docstring = ast.get_docstring(node)
        arg_helps = parse_docstring_args(docstring)

        arguments: list[CLIArgument] = []

        # Сопоставляем аргументы с дефолтными значениями
        args = node.args.args
        defaults = node.args.defaults
        offset = len(args) - len(defaults)

        for i, arg in enumerate(args):
            arg_name = arg.arg

            # Извлекаем тип из аннотации
            type_str = "str"
            if arg.annotation:
                type_str = ast.unparse(arg.annotation)

            # Извлекаем дефолтное значение
            default_str = None
            if i >= offset:
                default_node = defaults[i - offset]
                default_str = ast.unparse(default_node)

            help_text = arg_helps.get(arg_name)

            arguments.append(
                CLIArgument(
                    name=arg_name,
                    type_str=type_str,
                    default_str=default_str,
                    help_text=help_text,
                )
            )

        # Относительный путь для красоты отображения
        rel_path = file_path.relative_to(self.root_dir).as_posix()

        return CLICommandInfo(
            name=node.name,
            file_path=rel_path,
            docstring=docstring,
            arguments=arguments,
        )
