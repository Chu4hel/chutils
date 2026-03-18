"""
Пример 6: Использование локальных переопределений конфигурации.

Этот пример демонстрирует механизм 'config.yml' + 'config.local.yml'.
Локальные файлы позволяют переопределять настройки (например, для разработки) 
не меняя основной файл конфигурации, который находится в git.
"""

import os
import shutil
from pathlib import Path

from chutils import config


def setup_demo_files(root: Path) -> None:
    """Создает имитацию структуры проекта с двумя файлами конфига."""
    root.mkdir(exist_ok=True)
    (root / "pyproject.toml").touch()  # Маркер корня проекта

    # Основной файл (то, что обычно лежит в репозитории)
    (root / "config.yml").write_text("""
App:
  name: ProductionApp
  version: 1.0
Database:
  host: db.production.com
  port: 5432
""", encoding='utf-8')

    # Локальный файл (то, что создается на машине разработчика)
    (root / "config.local.yml").write_text("""
App:
  version: 1.1-dev
Database:
  host: localhost
""", encoding='utf-8')


def main() -> None:
    """Демонстрирует приоритет локальных настроек над основными."""
    temp_dir = Path("./demo_config_override")
    setup_demo_files(temp_dir)

    original_cwd = os.getcwd()
    os.chdir(temp_dir)

    try:
        # Сбрасываем кэш, чтобы chutils заново нашел файлы в текущей папке
        config._config_loaded = False
        config._config_object = None
        config._paths_initialized = False

        print("--- Демонстрация слияния (Merge) конфигураций ---")

        # 1. Значение осталось из основного файла (т.к. в локальном его нет)
        app_name: str = config.get_config_value("App", "name")
        print(f"App Name: {app_name} (Взято из config.yml)")

        # 2. Значения переопределены локальным файлом
        app_version: str = config.get_config_value("App", "version")
        db_host: str = config.get_config_value("Database", "host")
        print(f"Version:  {app_version} (Переопределено локально)")
        print(f"DB Host:  {db_host} (Переопределено локально)")

        # 3. Значение типа int также сохранилось из основного
        db_port: int = config.get_config_int("Database", "port")
        print(f"DB Port:  {db_port} (Взято из config.yml)")

    finally:
        os.chdir(original_cwd)
        shutil.rmtree(temp_dir)
        print("\n[OK] Демонстрация завершена, временные файлы удалены.")


if __name__ == "__main__":
    main()
