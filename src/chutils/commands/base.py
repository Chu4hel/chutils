import argparse
from abc import ABC, abstractmethod


class BaseCommand(ABC):
    """
    Базовый класс для всех команд CLI.
    Определяет интерфейс для регистрации аргументов и выполнения команды.
    """

    @abstractmethod
    def register(self, subparsers: argparse._SubParsersAction):
        """
        Регистрирует подкоманду и её аргументы.
        
        Args:
            subparsers: Объект subparsers из основного парсера.
        """
        pass

    @abstractmethod
    def handle(self, args: argparse.Namespace):
        """
        Выполняет логику команды.
        
        Args:
            args: Распарсенные аргументы командной строки.
        """
        pass
