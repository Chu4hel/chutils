from __future__ import annotations

import argparse
from unittest.mock import MagicMock

import pytest

from chutils.commands.pypi import PyPiCommand


def test_pypi_command_parsing(monkeypatch, cli_runner):
    """Проверяет корректность парсинга аргументов команды pypi."""
    # Создаем mock для handle_check, чтобы проверить, что он вызывается с правильными аргументами
    mock_handle_check = MagicMock()
    monkeypatch.setattr(PyPiCommand, "handle_check", mock_handle_check)

    # 1. Запуск без параметров (должен вызвать check с дефолтами)
    result = cli_runner.invoke(["pypi"])
    assert result.exit_code == 0
    mock_handle_check.assert_called_once()
    
    args = mock_handle_check.call_args[0][0]
    assert args.subcommand is None or args.subcommand == "check"
    assert args.mirrors is None
    assert args.json is False
    assert args.package == "six"

    mock_handle_check.reset_mock()

    # 2. Запуск с флагами
    result = cli_runner.invoke([
        "pypi", "check", 
        "-m", "https://mirror1.com,https://mirror2.com",
        "--json",
        "--package", "requests"
    ])
    assert result.exit_code == 0
    mock_handle_check.assert_called_once()
    
    args = mock_handle_check.call_args[0][0]
    assert args.subcommand == "check"
    assert args.mirrors == "https://mirror1.com,https://mirror2.com"
    assert args.json is True
    assert args.package == "requests"
