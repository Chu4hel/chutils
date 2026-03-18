"""
Пример 3: Безопасное управление секретами.

Демонстрирует работу SecretManager: сохранение и получение секретов из
системного хранилища (keyring) и файлов .env с учетом приоритетов.
"""
import os

from chutils import SecretManager

# --- Подготовка ---
# Для чистоты примера убедимся, что переменная окружения не установлена
if "API_KEY_FROM_ENV" in os.environ:
    del os.environ["API_KEY_FROM_ENV"]


def main() -> None:
    """
    Демонстрирует способы хранения секретов и их приоритеты.
    """
    # Инициализация. Имя сервиса берется из config.yml (Secrets -> service_name).
    secrets = SecretManager()

    print("--- 1. Системное хранилище (Keyring) ---")
    # Этот метод сохраняет данные в безопасное хранилище ОС (Windows Credential Manager, и т.д.)
    db_key = "example_db_password"
    secrets.save_secret(db_key, "ValueFromKeyring_123")

    val: str = secrets.get_secret(db_key)
    print(f"Получен секрет из Keyring: {val}")

    print("\n--- 2. Использование .env файла ---")
    # SecretManager автоматически загружает .env из корня проекта.
    # Добавьте в ваш .env файл: DOTENV_SECRET="ValueFromDotEnv_456"
    # Это удобно для Docker-контейнеров или CI/CD.
    dotenv_val: str = secrets.get_secret("DOTENV_SECRET")
    if dotenv_val:
        print(f"Получен секрет из .env: {dotenv_val}")
    else:
        print("Секрет DOTENV_SECRET не найден в .env. (Проверьте наличие файла .env)")

    print("\n--- 3. Демонстрация приоритетов ---")
    # Если секрет существует в обоих местах, Keyring всегда побеждает.
    # Добавим в Keyring ключ, который (предположим) уже есть в .env
    shared_key = "SHARED_KEY"
    secrets.save_secret(shared_key, "I_AM_FROM_KEYRING")

    # Предположим, в .env написано: SHARED_KEY="I_AM_FROM_DOTENV"
    result: str = secrets.get_secret(shared_key)
    print(f"Поиск ключа '{shared_key}': {result}")
    print("Результат: Keyring имеет высший приоритет над .env и переменными окружения.")

    # Очистка для чистоты следующих запусков
    secrets.delete_secret(db_key)
    secrets.delete_secret(shared_key)


if __name__ == "__main__":
    main()
