# examples/03_secrets.py
from chutils import SecretManager

# 1. Инициализируем менеджер секретов для нашего примера.
# Важно использовать уникальное имя для каждого вашего приложения.
secrets = SecretManager("chutils_example_app")
secret_key = "api_token"
secret_value = "my_super_secret_token_12345"

# 2. Сохраняем секрет. Это нужно сделать один раз.
print(f"Сохраняем секрет для ключа '{secret_key}'...")
secrets.save_secret(secret_key, secret_value)
print("Секрет сохранен в системном хранилище.")

# 3. Получаем секрет в другом месте программы.
print(f"Получаем секрет для ключа '{secret_key}'...")
retrieved_value = secrets.get_secret(secret_key)

if retrieved_value:
    print(f"  -> Получено значение: {retrieved_value}")
    assert retrieved_value == secret_value
else:
    print("  -> Секрет не найден!")

# 4. Удаляем секрет после использования.
print(f"Удаляем секрет для ключа '{secret_key}'...")
secrets.delete_secret(secret_key)
print("Секрет удален.")

# 5. Убеждаемся, что он удален.
final_check = secrets.get_secret(secret_key)
if not final_check:
    print(f"Проверка: секрет для ключа '{secret_key}' действительно удален.")
