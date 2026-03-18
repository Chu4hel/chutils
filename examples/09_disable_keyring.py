"""
Пример 9: Отключение системного хранилища (Keyring).

Демонстрирует, как подавить предупреждения о недоступности Keyring
и использовать исключительно .env файлы или переменные окружения.
Крайне полезно для Docker-контейнеров, серверов и CI/CD систем.
"""

import os

from chutils import SecretManager


def main() -> None:
    """Запуск демонстрации 'бесшумного' режима SecretManager."""

    # --- Способ 1: Переменная окружения (приоритетный способ для Docker) ---
    # Установка этого флага полностью отключает попытки обращения к Keyring
    os.environ["CH_DISABLE_KEYRING_WARNING"] = "true"

    print("--- Вариант 1: Использование переменной окружения ---")
    secrets_env = SecretManager("docker_service")

    # Теперь, даже если Keyring не установлен в системе, вы не увидите 
    # предупреждений (WARNING) в консоли.
    val = secrets_env.get_secret("DB_PASSWORD")
    print(f"Поиск секрета: {val} (поиск выполнен только в .env и окружении)")

    # Удалим переменную для чистоты примера
    del os.environ["CH_DISABLE_KEYRING_WARNING"]

    # --- Способ 2: Файл конфигурации ---
    print("\n--- Вариант 2: Настройка через config.yml ---")
    print("Вы можете добавить в ваш файл конфигурации глобальный флаг:")
    print("secrets:")
    print("  disable_keyring: true")

    print("\nЭто удобно, если вы хотите отключить Keyring сразу для всего приложения.")


if __name__ == "__main__":
    main()
