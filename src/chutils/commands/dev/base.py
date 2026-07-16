from __future__ import annotations

import argparse
from abc import ABC, abstractmethod
from typing import Any

from chutils.cli_utils import get_console


class SubCommand(ABC):
    """
    Абстрактный базовый класс для подкоманд dev.
    
    Определяет общий интерфейс для регистрации и выполнения подкоманд.
    """

    def __init__(self) -> None:
        """Инициализирует базовую подкоманду, настраивая консоли вывода."""
        self.console = get_console()
        self.err_console = get_console(stderr=True)

    @abstractmethod
    def register(self, subparsers: argparse._SubParsersAction[Any]) -> None:
        """
        Регистрирует подкоманду, её описание и аргументы.
        
        Args:
            subparsers: Объект subparsers, полученный из ArgumentParser.add_subparsers().
        """
        pass

    @abstractmethod
    def handle(self, args: argparse.Namespace) -> None:
        """
        Основной метод выполнения подкоманды.
        
        Args:
            args: Объект Namespace с аргументами командной строки.
        """
        pass
