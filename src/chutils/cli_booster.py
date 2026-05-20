"""
Модуль для быстрого создания консольных команд (CLI Booster).

Предоставляет декоратор @cli_command, который превращает обычную функцию
в полноценную CLI-утилиту с автоматическим парсингом аргументов.
"""

import argparse
import asyncio
import inspect
import re
from functools import wraps
from pathlib import Path
from typing import Any, Callable, TypeVar, Dict

# Тип для декорируемой функции
F = TypeVar("F", bound=Callable[..., Any])


def cli_command(func: F) -> F:
    """
    Декоратор для превращения функции в CLI-команду.

    Интроспектирует сигнатуру функции и создает парсер аргументов argparse.
    Поддерживает аннотации типов, значения по умолчанию, асинхронные функции
    и автоматический парсинг докстрингов (Google-style) для генерации справки.

    Example:
        @cli_command
        def my_script(name: str, count: int = 1):
            \"""\n
            Пример скрипта.
            
            Args:
                name (str): Имя пользователя.
                count (int): Количество повторений.
            \"""\n
            for _ in range(count):
                print(f"Hello, {name}!")
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        # Если аргументы переданы явно (вызов из кода), просто вызываем функцию
        if args or kwargs:
            return _execute(func, *args, **kwargs)

        # Проверяем, запущен ли скрипт напрямую
        # Инспектируем кадр стека, который вызвал wrapper
        caller_frame = inspect.currentframe().f_back
        if caller_frame and caller_frame.f_globals.get("__name__") == "__main__":
            # Интроспекция сигнатуры и парсинг CLI
            sig = inspect.signature(func)
            parser = _create_parser(func, sig)

            # Парсинг аргументов CLI
            parsed_args = parser.parse_args()
            func_args = vars(parsed_args)
            return _execute(func, **func_args)

        # Если вызвано не из __main__, просто вызываем функцию без аргументов
        return _execute(func)

    return wrapper  # type: ignore


def _create_parser(func: Callable, sig: inspect.Signature) -> argparse.ArgumentParser:
    """Создает ArgumentParser на основе сигнатуры функции."""
    doc_help = _parse_docstring(func.__doc__)

    parser = argparse.ArgumentParser(
        description=func.__doc__.strip().split('\n\n')[0] if func.__doc__ else None,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    for name, param in sig.parameters.items():
        _add_argument(parser, name, param, doc_help.get(name))

    return parser


def _parse_docstring(docstring: str) -> Dict[str, str]:
    """
    Парсит docstring в стиле Google для извлечения описаний аргументов.
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


def _add_argument(parser: argparse.ArgumentParser, name: str, param: inspect.Parameter, help_text: str = None):
    """Добавляет аргумент в парсер на основе параметра функции."""
    name_cli = name.replace("_", "-")

    kwargs = {
        "help": help_text or f"Аргумент {name}",
    }

    # Позиционный или опциональный
    is_optional = param.default is not inspect.Parameter.empty

    # Определение типа
    annotation = param.annotation
    if annotation is inspect.Parameter.empty:
        # Пытаемся угадать тип по значению по умолчанию
        if is_optional:
            annotation = type(param.default)
        else:
            annotation = str

    # Обработка типов
    if annotation is bool:
        kwargs["action"] = "store_true" if not param.default else "store_false"
    elif hasattr(annotation, "__origin__") and annotation.__origin__ is list:
        # Обработка list[T]
        kwargs["nargs"] = "+"
        if annotation.__args__:
            kwargs["type"] = annotation.__args__[0]
    elif annotation is Path:
        kwargs["type"] = Path
    elif annotation in (int, float, str):
        kwargs["type"] = annotation

    if is_optional:
        parser.add_argument(f"--{name_cli}", default=param.default, **kwargs)
    else:
        parser.add_argument(name_cli, **kwargs)


def _execute(func: Callable, *args, **kwargs):
    """Выполняет функцию, учитывая её асинхронность."""
    if inspect.iscoroutinefunction(func):
        try:
            # Проверяем, есть ли запущенный цикл событий
            asyncio.get_running_loop()
            # Если мы уже в асинхронном цикле, возвращаем корутину для await
            return func(*args, **kwargs)
        except RuntimeError:
            # Если цикла нет (CLI или синхронный вызов), запускаем новый
            return asyncio.run(func(*args, **kwargs))
    return func(*args, **kwargs)
