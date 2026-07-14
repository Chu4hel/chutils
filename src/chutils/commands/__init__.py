"""
Пакет команд для CLI.
"""
from .base import BaseCommand


def get_commands() -> list[type[BaseCommand]]:
    """Возвращает список всех классов команд.

    Returns:
        Список классов, унаследованных от BaseCommand.
    """
    from .secrets import SecretsCommand
    from .init import InitCommand
    from .validate import ValidateCommand
    from .paths import ShowPathsCommand
    from .template import TemplateCommand
    from .config import ConfigCommand
    from .dev import DevCommand
    from .env import EnvCommand

    return [
        SecretsCommand,
        InitCommand,
        ValidateCommand,
        ShowPathsCommand,
        TemplateCommand,
        ConfigCommand,
        DevCommand,
        EnvCommand
    ]
