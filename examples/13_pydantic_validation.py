"""
Пример 13: Валидация конфигурации через Pydantic.

Этот пример демонстрирует, как использовать Pydantic модели для
строгой типизации и валидации загружаемых настроек.
"""

import os
from typing import List

from pydantic import BaseModel, Field, ValidationError

from chutils import config, get_config, get_config_section


class DbConfig(BaseModel):
    """Модель для секции базы данных."""
    host: str
    port: int
    pool_size: int = 10


class AppConfig(BaseModel):
    """Основная модель конфигурации."""
    app_name: str = Field(alias="name")
    version: str
    allowed_hosts: List[str]
    db: DbConfig = Field(alias="Database")


def main():
    # Создадим временный файл конфигурации для демонстрации
    config_content = """
name: MySuperApp
version: "2.5.0"
allowed_hosts:
  - localhost
  - 127.0.0.1
Database:
  host: "db.internal"
  port: 5432
"""
    with open("config.yml", "w", encoding="utf-8") as f:
        f.write(config_content)

    # Сбрасываем кэш, чтобы подхватить новый файл
    config._cm._reset()

    print("--- Валидация всего конфига ---")
    try:
        # Загружаем конфиг сразу в модель
        app_cfg = get_config(model=AppConfig)
        print(f"Приложение: {app_cfg.app_name} v{app_cfg.version}")
        print(f"Разрешенные хосты: {', '.join(app_cfg.allowed_hosts)}")
        print(f"БД Хост: {app_cfg.db.host}")
    except ValidationError as e:
        print(f"Ошибка валидации конфига: {e}")

    print("\n--- Валидация отдельной секции ---")
    try:
        db_cfg = get_config_section("Database", model=DbConfig)
        print(f"Секция БД провалидирована: {db_cfg}")
    except ValidationError as e:
        print(f"Ошибка в секции БД: {e}")

    print("\n--- Пример ошибки валидации ---")
    # Изменим порт на некорректный тип
    with open("config.yml", "w", encoding="utf-8") as f:
        f.write(config_content.replace("port: 5432", "port: 'not-an-int'"))

    config._cm._reset()

    try:
        get_config(model=AppConfig)
    except ValidationError as e:
        print("Перехвачена ожидаемая ошибка валидации:")
        print(e)

    # Уборка
    if os.path.exists("config.yml"):
        os.remove("config.yml")


if __name__ == "__main__":
    main()
