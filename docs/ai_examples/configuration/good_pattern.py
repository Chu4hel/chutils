"""
Паттерн: Использование Pydantic моделей, централизованной конфигурации и SecretManager.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from chutils import get_config_value, SecretManager


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
        print(f"Connecting to {self.config.host}:{self.config.port} as {self.config.username}")


def initialize_database() -> DatabaseConnection:
    """Инициализирует настройки и создает подключение к БД.

    Returns:
        Экземпляр DatabaseConnection.
    """
    # 1. Читаем и валидируем конфигурацию из config.yml (с поддержкой env оверрайдов)
    # Используем get_config_value с Pydantic моделью в качестве fallback
    db_config = get_config_value("Database", model=DatabaseConfig)

    # 2. Безопасно получаем секрет (пароль) из SecretManager (keyring -> .env)
    secret_mgr = SecretManager(service_name="my_app")
    db_password = secret_mgr.get("db_password", default="temporary_dev_password")

    # 3. Инжектируем настройки в подключение
    return DatabaseConnection(config=db_config, password=db_password)
