"""
Паттерн: Правильная обработка исключений и сохранение контекста ошибок.
"""

from __future__ import annotations

from chutils.exceptions import ChutilsException


class ConfigLoadError(ChutilsException):
    """Исключение при невозможности прочитать файл конфигурации."""
    pass


class InvalidPortError(ChutilsException):
    """Исключение при некорректном формате порта."""
    pass


def read_system_config(file_path: str) -> str:
    """Читает конфигурационный файл с диска.

    Args:
        file_path: Путь к файлу конфигурации.

    Returns:
        Содержимое конфигурационного файла в виде строки.

    Raises:
        ConfigLoadError: Если файл не найден или нет прав на чтение.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError as e:
        # Хорошо: Пробрасываем специализированную ошибку с сохранением оригинального контекста (from e)
        raise ConfigLoadError(f"Файл конфигурации не найден по пути: {file_path}") from e
    except PermissionError as e:
        raise ConfigLoadError(f"Нет прав для чтения файла конфигурации: {file_path}") from e


def parse_port(port_str: str) -> int:
    """Парсит строковое представление порта в число.

    Args:
        port_str: Строка с портом (например, "8080").

    Returns:
        Целочисленный номер порта.

    Raises:
        InvalidPortError: Если передан некорректный формат порта.
    """
    try:
        port = int(port_str)
        if not (1 <= port <= 65535):
            raise InvalidPortError(f"Номер порта вне допустимого диапазона (1-65535): {port}")
        return port
    except ValueError as e:
        # Хорошо: Локализованный перехват и информативное исключение
        raise InvalidPortError(f"Некорректное строковое представление порта: '{port_str}'") from e
