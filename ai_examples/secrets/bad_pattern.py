"""
Антипаттерн: Небезопасное получение секретов без валидации.
"""

import os


def get_api_token() -> str:
    # Плохо: Секрет читается из открытого окружения — может логироваться в CI/CD.
    token = os.getenv("API_TOKEN")

    # Плохо: Нет проверки на None/пустую строку — ошибка проявится позже
    # в виде невнятного AttributeError или HTTP 401 без объяснений.
    return token  # type: ignore[return-value]


def get_database_password() -> str:
    # Плохо: Захардкоженный fallback в production-коде — секрет попадёт в репозиторий.
    password = os.getenv("DB_PASSWORD", "admin123")

    # Плохо: Нет различия между dev/production окружениями.
    # Плохо: Нет аудит-трейла — никто не знает, когда и где был использован секрет.
    return password


class ApiClient:
    # Плохо: Секрет хранится в атрибуте класса как plain text.
    # Плохо: Нет type hints, нет docstring.
    def __init__(self):
        self.token = os.getenv("API_TOKEN", "hardcoded_fallback_token")

    def request(self, endpoint: str) -> None:
        # Плохо: Токен логируется в открытом виде.
        print(f"Запрос к {endpoint} с токеном {self.token}")
