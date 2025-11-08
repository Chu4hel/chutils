# examples/06_local_config_override.py
import os
from pathlib import Path
from chutils import config

# --- Подготовка: Создаем фейковые файлы конфигурации ---
# В реальном приложении эти файлы будут существовать в корне вашего проекта.

# Создаем временную директорию для имитации корня проекта
temp_project_root = Path("./temp_project_for_config_override")
temp_project_root.mkdir(exist_ok=True)

# Создаем основной config.yml
main_config_content = """
App:
  name: MainApp
  version: 1.0
  settings:
    debug: false
    log_level: INFO
Database:
  host: production_db.com
  port: 5432
"""
(temp_project_root / "config.yml").write_text(main_config_content)

# Создаем локальный config.local.yml
local_config_content = """
App:
  version: 1.1
  settings:
    debug: true
Database:
  host: localhost
  user: local_user
"""
(temp_project_root / "config.local.yml").write_text(local_config_content)

# Создаем маркер проекта, чтобы chutils нашел корень
(temp_project_root / "pyproject.toml").touch()

# Переходим во временную директорию, чтобы chutils нашел файлы
original_cwd = os.getcwd()
os.chdir(temp_project_root)

# --- Демонстрация ---

print("--- Демонстрация переопределения конфигурации локальным файлом ---")

# Сбрасываем кэш chutils.config, чтобы он перечитал файлы
config._config_loaded = False
config._config_object = None
config._paths_initialized = False

# Загружаем конфигурацию
cfg = config.get_config()

print("\nОбъединенная конфигурация:")
print(config.yaml.dump(cfg, indent=2, allow_unicode=True, sort_keys=False))

print("\nПроверки:")
# Значения из основного файла, не переопределенные
assert config.get_config_value("App", "name") == "MainApp"
print(f"App.name: {config.get_config_value('App', 'name')} (Ожидается: MainApp - из основного)")

# Значения, переопределенные локальным файлом
assert config.get_config_float("App", "version") == 1.1
print(f"App.version: {config.get_config_float('App', 'version')} (Ожидается: 1.1 - переопределено локальным)")

# Вложенные значения, переопределенные локальным файлом
assert config.get_config_boolean("App", "settings", "debug") is True
print(f"App.settings.debug: {config.get_config_boolean('App', 'settings', 'debug')} (Ожидается: True - переопределено локальным)")

# Значения из основного файла, не затронутые локальным
assert config.get_config_value("App", "settings", "log_level") == "INFO"
print(f"App.settings.log_level: {config.get_config_value('App', 'settings', 'log_level')} (Ожидается: INFO - из основного)")

# Новое значение, добавленное локальным файлом
assert config.get_config_value("Database", "user") == "local_user"
print(f"Database.user: {config.get_config_value('Database', 'user')} (Ожидается: local_user - добавлено локальным)")

# Значение из основного файла, переопределенное локальным
assert config.get_config_value("Database", "host") == "localhost"
print(f"Database.host: {config.get_config_value('Database', 'host')} (Ожидается: localhost - переопределено локальным)")

print("\n--- Демонстрация завершена ---")

# --- Очистка ---
os.chdir(original_cwd) # Возвращаемся в исходную директорию
for f in temp_project_root.iterdir():
    f.unlink()
temp_project_root.rmdir()
print("Временные файлы и директория удалены.")