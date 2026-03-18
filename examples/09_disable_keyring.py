"""
Пример использования SecretManager с отключенным системным хранилищем (keyring).

Этот пример демонстрирует, как подавить предупреждения о недоступности keyring
и переключиться на использование только .env файлов и переменных окружения.
"""

import os

from chutils.secret_manager import SecretManager


def main():
    # --- Способ 1: Через переменную окружения ---
    # Это полезно для Docker/CI-CD сред.
    os.environ["CH_DISABLE_KEYRING_WARNING"] = "true"

    print("--- Способ 1: Отключение через переменную окружения ---")
    # Инициализируем SecretManager. Варнинг о недоступности keyring не появится.
    secrets_env = SecretManager("example_env_service")

    # Пытаемся получить секрет (будет искать только в .env и окружении)
    val = secrets_env.get_secret("SOME_API_KEY")
    print(f"Секрет SOME_API_KEY: {val}")
    print()

    # --- Способ 2: Через файл конфигурации ---
    # В config.yml (или config.local.yml) добавьте:
    # secrets:
    #   disable_keyring: true

    print("--- Способ 2: Отключение через config.yml ---")
    print("Добавьте в ваш config.yml:")
    print("secrets:")
    print("  disable_keyring: true")
    print()

    # Очистим переменную для чистоты эксперимента (если бы мы использовали конфиг)
    del os.environ["CH_DISABLE_KEYRING_WARNING"]

    # Примечание: В реальном приложении настройка из конфига подхватится автоматически.
    print("Теперь SecretManager будет следовать настройкам из вашего конфигурационного файла.")


if __name__ == "__main__":
    main()
