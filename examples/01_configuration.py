# examples/01_configuration.py
from chutils import get_config_value, get_config_int
import os

# chutils автоматически найдет config.yml в этой же папке
# или в корне проекта, если запустить оттуда.
print(f"Пример запущен из директории: {os.getcwd()}")

db_host = get_config_value("Database", "host", fallback="127.0.0.1")
db_port = get_config_int("Database", "port", fallback=5433)
db_user = get_config_value("Database", "user")

print("Читаем конфигурацию из 'config.yml':")
print(f"  - Хост БД: {db_host}")
print(f"  - Порт БД: {db_port}")
print(f"  - Пользователь БД: {db_user}")

# Пример получения несуществующего значения с fallback
api_key = get_config_value("API", "key", fallback="Ключ не найден")
print(f"  - Ключ API: {api_key}")
