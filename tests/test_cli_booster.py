import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from chutils.cli_booster import cli_command


def test_cli_command_basic():
    @cli_command
    def greet(name: str, count: int = 1):
        return f"Hello, {name}!" * count

    # Обычный вызов
    assert greet("Alice") == "Hello, Alice!"
    assert greet(name="Bob", count=2) == "Hello, Bob!Hello, Bob!"


def test_cli_command_parsing():
    @cli_command
    def app(name: str, age: int, is_admin: bool = False):
        return {"name": name, "age": age, "is_admin": is_admin}

    # Симулируем вызов из __main__
    with patch("inspect.currentframe") as mock_frame:
        mock_frame.return_value.f_back.f_globals = {"__name__": "__main__"}
        with patch.object(sys, "argv", ["script.py", "Alice", "30", "--is-admin"]):
            result = app()
            assert result == {"name": "Alice", "age": 30, "is_admin": True}


def test_cli_command_list_and_path(tmp_path):
    @cli_command
    def files(paths: list[Path], verbose: bool = True):
        return {"paths": paths, "verbose": verbose}

    with patch("inspect.currentframe") as mock_frame:
        mock_frame.return_value.f_back.f_globals = {"__name__": "__main__"}
        with patch.object(sys, "argv", ["script.py", "/tmp/1", "/tmp/2"]):
            result = files()
            assert len(result["paths"]) == 2
            assert isinstance(result["paths"][0], Path)
            assert result["verbose"] is True


@pytest.mark.asyncio
async def test_cli_command_async_direct():
    @cli_command
    async def async_app(val: int):
        return val * 2

    # Обычный вызов
    assert await async_app(10) == 20


def test_cli_command_async_cli():
    @cli_command
    async def async_app(val: int):
        return val * 2

    # CLI вызов (через asyncio.run внутри)
    with patch("inspect.currentframe") as mock_frame:
        mock_frame.return_value.f_back.f_globals = {"__name__": "__main__"}
        with patch.object(sys, "argv", ["script.py", "5"]):
            result = async_app()
            assert result == 10


def test_cli_command_no_annotations():
    @cli_command
    def no_types(a, b=10):
        return f"{a}-{b}"

    with patch("inspect.currentframe") as mock_frame:
        mock_frame.return_value.f_back.f_globals = {"__name__": "__main__"}
        with patch.object(sys, "argv", ["script.py", "val1", "--b", "20"]):
            result = no_types()
            assert result == "val1-20"


def test_cli_command_docstring_parsing():
    @cli_command
    def documented(name: str, age: int = 18):
        """
        Тестовая функция.

        Args:
            name (str): Имя пользователя.
            age (int): Возраст пользователя.
        """
        return f"{name}-{age}"

    # Проверяем через создание парсера напрямую
    import inspect
    from chutils.cli_booster import _create_parser

    sig = inspect.signature(documented)
    parser = _create_parser(documented, sig)

    # Ищем аргументы в парсере
    actions = {a.dest: a.help for a in parser._actions}
    assert actions["name"] == "Имя пользователя."
    assert actions["age"] == "Возраст пользователя."
    assert parser.description == "Тестовая функция."
