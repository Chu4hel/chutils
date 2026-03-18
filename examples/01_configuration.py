"""
Пример 1: Базовая работа с конфигурацией.

Этот пример демонстрирует, как получать значения различных типов из файлов
конфигурации (поддерживаются форматы YAML и INI). 
Библиотека автоматически ищет файлы config.yml, config.yaml или config.ini.
"""

import os

from chutils import get_config_value, get_config_int


def main() -> None:
    """
    Демонстрирует чтение строковых и целочисленных значений с использованием fallback.
    """
    print(f"Запуск примера из: {os.getcwd()}\n")

    # 1. Чтение строкового значения. Если ключа нет - вернет '127.0.0.1'
    db_host: str = get_config_value("Database", "host", fallback="127.0.0.1")

    # 2. Чтение целого числа. Автоматически преобразует тип.
    db_port: int = get_config_int("Database", "port", fallback=5432)

    # 3. Чтение без значения по умолчанию. Вернет None, если секция или ключ отсутствуют.
    db_user: str = get_config_value("Database", "user")

    print("--- Результаты чтения config.yml ---")
    print(f"Хост БД: {db_host}")
    print(f"Порт БД: {db_port}")
    print(f"Пользователь: {db_user}")

    # 4. Демонстрация fallback для отсутствующих данных
    api_key: str = get_config_value("API", "secret_key", fallback="DEMO_KEY_MISSING")
    print(f"Ключ API (fallback): {api_key}")


if __name__ == "__main__":
    main()
