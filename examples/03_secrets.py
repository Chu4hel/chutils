# examples/03_secrets.py
import os

from chutils import SecretManager

# --- Подготовка ---
# Для чистоты примера убедимся, что переменная окружения не установлена
if "API_KEY_FROM_ENV" in os.environ:
    del os.environ["API_KEY_FROM_ENV"]

# 1. Инициализируем менеджер секретов для нашего примера.
# Важно использовать уникальное имя для каждого вашего приложения.
secrets = SecretManager("chutils_example_app")

# --- Демонстрация приоритета ---

print("--- 1. Поиск секрета, который есть только в keyring ---")
keyring_key = "my_keyring_secret"
secrets.save_secret(keyring_key, "value_from_keyring")
print(f"  -> Результат для '{keyring_key}': {secrets.get_secret(keyring_key)}")
secrets.delete_secret(keyring_key)  # Очистка
print("-" * 20)

print("\n--- 2. Поиск секрета, который есть только в .env файле ---")

# Для этого теста убедитесь, что в папке `examples` есть файл `.env`
# с содержимым: DOTENV_SECRET="value_from_dotenv_file"

dotenv_key = "DOTENV_SECRET"

print(f"  -> Результат для '{dotenv_key}': {secrets.get_secret(dotenv_key)}")
print("-" * 20)
print("\n--- 3. Поиск секрета, который есть и в keyring, и в .env ---")

shared_key = "SHARED_KEY"

# Сохраняем значение в keyring
secrets.save_secret(shared_key, "value_from_keyring_wins")

# Для этого теста убедитесь, что в папке `examples` есть файл `.env`
# с содержимым: SHARED_KEY="value_from_dotenv_loses"

print(f"  -> Результат для '{shared_key}': {secrets.get_secret(shared_key)} (keyring имеет приоритет)")

secrets.delete_secret(shared_key)  # Очистка

print("-" * 20)

print("\n--- 4. Поиск несуществующего секрета ---")
non_existent_key = "I_DO_NOT_EXIST"
print(f"  -> Результат для '{non_existent_key}': {secrets.get_secret(non_existent_key)}")
print("-" * 20)
