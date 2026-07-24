"""
Тесты для подкоманды CLI 'chutils dev watch'.
"""

import argparse
from unittest.mock import MagicMock, patch

import pytest

from chutils.commands.dev import DevCommand
from chutils.commands.dev.watch import WatchSubCommand


def test_dev_watch_parser_args() -> None:
    """Проверяет разбор аргументов командной строки для dev watch."""
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")
    dev_cmd = DevCommand()
    dev_cmd.register(subparsers)

    # Проверка разбора флагов -p, -e, --ignore, -d и команды после '--'
    cmd_args = [
        "dev",
        "watch",
        "-p",
        "src",
        "-p",
        "tests",
        "-e",
        "py,yaml",
        "--ignore",
        ".git,.venv",
        "-d",
        "0.3",
        "--",
        "python",
        "main.py",
    ]
    parsed = parser.parse_args(cmd_args)

    assert parsed.subcommand == "watch"
    assert parsed.paths == ["src", "tests"]
    assert parsed.extensions == "py,yaml"
    assert parsed.ignore == ".git,.venv"
    assert parsed.debounce == 0.3
    assert parsed.command == ["--", "python", "main.py"]


def test_watch_subcommand_handle_subprocess() -> None:
    """Проверяет запуск процесса в WatchSubCommand.handle."""
    cmd = WatchSubCommand()
    args = argparse.Namespace(
        paths=["src"],
        extensions="py",
        ignore=None,
        debounce=0.1,
        module=None,
        command=["--", "python", "app.py"],
    )

    with patch("chutils.commands.dev.watch.SubprocessRunner") as mock_runner_cls, \
         patch("chutils.commands.dev.watch.get_watcher") as mock_get_watcher:
        mock_runner = MagicMock()
        mock_runner_cls.return_value = mock_runner
        mock_watcher = MagicMock()
        mock_watcher.is_running = False
        mock_get_watcher.return_value = mock_watcher

        cmd.handle(args)

        mock_runner_cls.assert_called_once_with(command=["python", "app.py"])
        mock_runner.start.assert_called_once()
        mock_watcher.start.assert_called_once()
        mock_watcher.stop.assert_called_once()
        mock_runner.stop.assert_called_once()


def test_watch_subcommand_handle_module() -> None:
    """Проверяет запуск в режиме модуля (-m) в WatchSubCommand.handle."""
    cmd = WatchSubCommand()
    args = argparse.Namespace(
        paths=None,
        extensions=None,
        ignore=None,
        debounce=0.1,
        module="myapp.main:start",
        command=None,
    )

    with patch("chutils.commands.dev.watch.InProcessReloader") as mock_reloader_cls, \
         patch("chutils.commands.dev.watch.get_watcher") as mock_get_watcher:
        mock_reloader = MagicMock()
        mock_reloader_cls.return_value = mock_reloader
        mock_watcher = MagicMock()
        mock_watcher.is_running = False
        mock_get_watcher.return_value = mock_watcher

        cmd.handle(args)

        mock_reloader_cls.assert_called_once_with(target="myapp.main:start")
        mock_reloader.start.assert_called_once()


def test_watch_subcommand_error_when_no_target() -> None:
    """Проверяет завершение с ошибкой, если не передана ни команда, ни модуль."""
    cmd = WatchSubCommand()
    args = argparse.Namespace(
        paths=None,
        extensions=None,
        ignore=None,
        debounce=0.1,
        module=None,
        command=None,
    )

    with pytest.raises(SystemExit) as exc:
        cmd.handle(args)
    assert exc.value.code == 1
