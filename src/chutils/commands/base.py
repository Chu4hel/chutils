import argparse
from abc import ABC, abstractmethod


class BaseCommand(ABC):
    """
    Абстрактный базовый класс для всех команд CLI chutils.
    
    Определяет единый интерфейс для регистрации подкоманд в argparse
    и выполнения связанной с ними бизнес-логики.
    """

    @abstractmethod
    def register(self, subparsers: argparse._SubParsersAction):
        """
        Регистрирует подкоманду, её описание и аргументы в основном парсере.
        
        Args:
            subparsers: Объект subparsers, полученный из ArgumentParser.add_subparsers().
        """
        pass

    @abstractmethod
    def handle(self, args: argparse.Namespace):
        """
        Основной метод выполнения команды.
        
        Вызывается диспетчером CLI после успешного парсинга аргументов.
        
        Args:
            args: Объект Namespace с распарсенными аргументами командной строки.
        """
        pass
