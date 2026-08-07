"""
Паттерн: Использование Pydantic моделей, централизованной конфигурации и SecretManager.

Демонстрирует:
- get_config_section с Pydantic-моделью и многоуровневым слиянием
- Строгий режим (required=True) — ConfigKeyNotFoundError при отсутствии ключа
- SecretManager с fallback и required-режимом (v3.0.0+)
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from chutils import SecretManager, get_config_section
from chutils.exceptions import ConfigKeyNotFoundError


class DatabaseConfig(BaseModel):
    """Схема конфигурации базы данных с валидацией."""

    host: str = Field(default="localhost", description="Хост базы данных")
    port: int = Field(default=5432, ge=1, le=65535, description="Порт базы данных")
    username: str = Field(default="postgres", description="Имя пользователя")


class DatabaseConnection:
    """Класс подключения к базе данных.

    Использует Dependency Inversion, принимая готовую конфигурацию.
    """

    def __init__(self, config: DatabaseConfig, password: str) -> None:
        """Инициализирует подключение.

        Args:
            config: Объект валидированной конфигурации базы данных.
            password: Безопасно полученный пароль для подключения.
        """
        self.config = config
        self.password = password

    def connect(self) -> None:
        """Эмулирует подключение к базе данных."""
        print(
            f"Connecting to {self.config.host}:{self.config.port} as {self.config.username}"
        )


def initialize_database() -> DatabaseConnection:
    """Инициализирует настройки и создает подключение к БД.

    Returns:
        Экземпляр DatabaseConnection.

    Raises:
        ConfigKeyNotFoundError: Если обязательный ключ отсутствует в конфигурации.
    """
    # 1. Читаем и валидируем конфигурацию из config.yml (с поддержкой env оверрайдов)
    db_config = get_config_section("Database", model=DatabaseConfig)

    # 2. Хорошо: required=True — явно сигнализирует, что ключ обязателен.
    #    При отсутствии возбуждается ConfigKeyNotFoundError (v3.0.0+), а не возвращается None.
    try:
        env_name = get_config_section("App", required=True)  # type: ignore[arg-type]
    except ConfigKeyNotFoundError as e:
        raise ConfigKeyNotFoundError(
            f"Секция '[App]' обязательна в config.yml. {e}"
        ) from e

    # 3. Безопасно получаем секрет (пароль) из SecretManager
    secret_mgr = SecretManager(service_name="my_app")

    # fallback используем только для dev-окружения:
    db_password = secret_mgr.get_secret(
        "db_password", fallback="temporary_dev_password"
    )

    # В production используем required=True — SecretNotFoundError при отсутствии:
    # db_password = secret_mgr.get_secret("db_password", required=True)

    # 4. Инжектируем настройки в подключение (DIP — не знает, откуда данные)
    del env_name  # используется только для примера выше
    return DatabaseConnection(config=db_config, password=db_password)
