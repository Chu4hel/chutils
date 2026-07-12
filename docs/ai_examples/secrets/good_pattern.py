"""
Паттерн: Правильное получение секретов через SecretManager (v3.0.0+).

Демонстрирует:
- Строгий режим required=True с SecretNotFoundError
- fallback только для dev/test окружений
- Асинхронное получение секретов через aget_secret
"""

from __future__ import annotations

from chutils import SecretManager
from chutils.exceptions import SecretNotFoundError


def get_api_token(env: str = "production") -> str:
    """Получает API-токен из безопасного хранилища.

    Args:
        env: Текущее окружение ('production' или 'development').

    Returns:
        API-токен в виде строки.

    Raises:
        SecretNotFoundError: Если секрет обязателен и не найден (production).
    """
    secret_mgr = SecretManager(service_name="my_app")

    if env == "production":
        # Хорошо: required=True в production — явная ошибка при отсутствии секрета.
        # SecretNotFoundError содержит hint с инструкцией по исправлению.
        try:
            return secret_mgr.get_secret("api_token", required=True)
        except SecretNotFoundError as e:
            raise SecretNotFoundError(
                f"Секрет 'api_token' обязателен в production-окружении. {e}"
            ) from e
    else:
        # Хорошо: fallback только для dev/test, никогда не для production.
        return secret_mgr.get_secret("api_token", fallback="dev_token_local")


async def get_api_token_async() -> str:
    """Асинхронно получает API-токен (для async-приложений).

    Returns:
        API-токен в виде строки.

    Raises:
        SecretNotFoundError: Если токен не найден в хранилище.
    """
    secret_mgr = SecretManager(service_name="my_app")
    # Хорошо: aget_secret — неблокирующая версия для asyncio-приложений
    return await secret_mgr.aget_secret("api_token", required=True)
