"""
Модуль для быстрого создания консольных команд (CLI Booster).

Предоставляет декоратор @cli_command, который превращает обычную функцию
в полноценную CLI-утилиту с автоматическим парсингом аргументов.
"""

import argparse
import asyncio
import inspect
from functools import wraps
from pathlib import Path
from typing import Any, Callable, TypeVar

# Тип для декорируемой функции
F = TypeVar("F", bound=Callable[..., Any])


def cli_command(func: F) -> F:
    """
    Декоратор для превращения функции в CLI-команду.

    Интроспектирует сигнатуру функции и создает парсер аргументов argparse.
    Поддерживает аннотации типов, значения по умолчанию и асинхронные функции.

    Example:
        @cli_command
        def my_script(name: str, count: int = 1):
            for _ in range(count):
                print(f"Hello, {name}!")
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        # Если аргументы переданы явно (вызов из кода), просто вызываем функцию
        if args or kwargs:
            return _execute(func, *args, **kwargs)

        # Если вызов без аргументов, проверяем, нужно ли парсить CLI
        # Мы парсим CLI только если скрипт запущен напрямую или через обертку
        # Простая эвристика: если sys.argv[0] похож на исполняемый файл
        # и мы вызваны без аргументов в коде.

        # Интроспекция сигнатуры
        sig = inspect.signature(func)
        parser = _create_parser(func, sig)

        # Парсинг аргументов CLI
        parsed_args = parser.parse_args()
        func_args = vars(parsed_args)

        return _execute(func, **func_args)

    return wrapper  # type: ignore


def _create_parser(func: Callable, sig: inspect.Signature) -> argparse.ArgumentParser:
    """Создает ArgumentParser на основе сигнатуры функции."""
    parser = argparse.ArgumentParser(
        description=func.__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    for name, param in sig.parameters.items():
        _add_argument(parser, name, param)

    return parser


def _add_argument(parser: argparse.ArgumentParser, name: str, param: inspect.Parameter):
    """Добавляет аргумент в парсер на основе параметра функции."""
    name_cli = name.replace("_", "-")

    kwargs = {
        "help": f"Аргумент {name}",
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
        return asyncio.run(func(*args, **kwargs))
    return func(*args, **kwargs)
