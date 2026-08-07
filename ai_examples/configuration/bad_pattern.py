"""
Антипаттерн: Ручное чтение конфигурации через os.environ без валидации.
"""

import os


class DatabaseConnection:
    # Плохо: Нет типизации и docstring.
    def __init__(self):
        # Плохо: Прямое чтение переменных окружения посреди бизнес-логики.
        # Плохо: Смешивание логики конфигурации и подключения к БД.
        # Плохо: Отсутствие проверки типов (порт читается как строка, а нужен int).
        self.host = os.getenv("DB_HOST", "localhost")
        self.port = os.getenv("DB_PORT", "5432")
        self.username = os.getenv("DB_USER", "postgres")
        self.password = os.getenv("DB_PASSWORD")  # Плохо: Секрет читается из открытых переменных окружения.

    def connect(self):
        print(f"Connecting to {self.host}:{self.port} as {self.username}")
