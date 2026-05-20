"""
Пакет команд для CLI.
"""
from typing import List, Type

from .base import BaseCommand


def get_commands() -> List[Type[BaseCommand]]:
    """
    Возвращает список всех классов команд.
    """
    from .secrets import SecretsCommand
    from .init import InitCommand
    from .validate import ValidateCommand
    from .paths import ShowPathsCommand
    from .template import TemplateCommand
    from .config import ConfigCommand

    return [
        SecretsCommand,
        InitCommand,
        ValidateCommand,
        ShowPathsCommand,
        TemplateCommand,
        ConfigCommand
    ]
