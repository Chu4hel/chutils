"""
Пакет команд для CLI.
"""

from .base import BaseCommand


def get_commands() -> list[type[BaseCommand]]:
    """Возвращает список всех классов команд.

    Returns:
        Список классов, унаследованных от BaseCommand.
    """
    from .check import CheckCommand
    from .config import ConfigCommand
    from .db import DbCommand
    from .dev import DevCommand
    from .env import EnvCommand
    from .init import InitCommand
    from .paths import ShowPathsCommand
    from .pypi import PyPiCommand
    from .secrets import SecretsCommand
    from .template import TemplateCommand
    from .validate import ValidateCommand

    return [
        SecretsCommand,
        InitCommand,
        ValidateCommand,
        CheckCommand,
        ShowPathsCommand,
        TemplateCommand,
        ConfigCommand,
        DevCommand,
        EnvCommand,
        PyPiCommand,
        DbCommand,
    ]
