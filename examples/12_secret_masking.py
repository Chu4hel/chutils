"""
Пример маскирования секретов в логах.

Этот скрипт демонстрирует, как библиотека chutils автоматически предотвращает
утечку чувствительных данных в логи.
"""

import os

from chutils.logger import setup_logger
from chutils.secret_manager import SecretManager

# 1. Настраиваем логгер
logger = setup_logger("masking_example", log_level="INFO")


def run_example():
    print("--- Демонстрация маскирования секретов ---")

    # --- Сценарий 1: Ручное добавление маски ---
    my_api_key = "sk-12345abcde67890"
    logger.add_mask(my_api_key)

    print("\n1. Ручное маскирование:")
    logger.info(f"Отправка запроса с ключом: {my_api_key}")
    # В консоли/файле будет: "Отправка запроса с ключом: ***"

    # --- Сценарий 2: Автоматическое маскирование через SecretManager ---
    # Добавим временную переменную окружения для примера
    os.environ["DATABASE_URL"] = "postgresql://user:password123@localhost:5432/mydb"

    # Инициализируем менеджер секретов
    secrets = SecretManager("example_app")

    # При получении секрета он автоматически попадает в фильтр маскирования
    db_uri = secrets.get_secret("DATABASE_URL")

    print("\n2. Автоматическое маскирование (SecretManager):")
    logger.info(f"Подключение к БД: {db_uri}")
    # В логах пароль будет скрыт: "postgresql://user:***@localhost:5432/mydb"

    # --- Сценарий 3: Отключение маскирования ---
    print("\n3. Отключение маскирования через ENV (CH_DISABLE_LOG_MASKING=true):")
    os.environ["CH_DISABLE_LOG_MASKING"] = "true"
    logger.info(f"Теперь секреты видны (для отладки): {my_api_key}")

    print("\nПроверьте вывод логов выше. Секреты в пунктах 1 и 2 должны быть заменены на ***")


if __name__ == "__main__":
    run_example()
