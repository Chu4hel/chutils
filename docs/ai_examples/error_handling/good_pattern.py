"""
Паттерн: Правильная обработка исключений, OptionalDependencyError и сохранение контекста ошибок.

Демонстрирует (v3.0.0+):
- Наследование кастомных исключений от ChutilsException с полями context/hint
- Правильный перехват OptionalDependencyError вместо RuntimeError
- Сохранение оригинального traceback через `raise ... from e`
"""

from __future__ import annotations

from chutils.exceptions import ChutilsException, OptionalDependencyError


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
        raise ConfigLoadError(
            f"Файл конфигурации не найден по пути: {file_path}",
            context={"path": file_path},
            hint="Убедитесь, что config.yml существует в корне проекта.",
        ) from e
    except PermissionError as e:
        raise ConfigLoadError(
            f"Нет прав для чтения файла конфигурации: {file_path}"
        ) from e


def parse_port(port_str: str) -> int:
    """Парсит строковое представление порта в число.

    Args:
        port_str: Строка с портом (например, \"8080\").

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
        raise InvalidPortError(
            f"Некорректное строковое представление порта: '{port_str}'",
            hint="Порт должен быть числом от 1 до 65535.",
        ) from e


def use_crypto_feature() -> str:
    """Пример правильного перехвата OptionalDependencyError (v3.0.0+).

    Returns:
        Результат шифрования или заглушка при отсутствии зависимости.
    """
    try:
        from chutils.crypto import encrypt_portable
        return encrypt_portable("secret_data", seed="my_seed")
    except OptionalDependencyError as e:
        # Хорошо: Перехватываем специфичную ошибку отсутствия зависимости.
        # e.hint содержит команду установки: "pip install chutils[crypto]"
        print(f"Функция шифрования недоступна: {e.message}")
        print(f"Совет: {e.hint}")
        return ""
