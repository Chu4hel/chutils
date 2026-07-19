"""
Пример 16: Поддержка Cloud Secret Managers.

Демонстрирует использование AWS Secrets Manager и GCP Secret Manager
в качестве провайдеров для SecretManager.
"""

import os

from chutils import SecretManager
from chutils.exceptions import OptionalDependencyError
from chutils.secret_manager.providers import (
    AWSSecretManagerProvider,
    EnvProvider,
    GCPSecretManagerProvider,
)


def main() -> None:
    """Демонстрирует интеграцию с облачными менеджерами секретов и цепочку fallback."""
    print("--- Инициализация облачных провайдеров секретов ---")

    # 1. Создаем провайдеры для AWS и GCP.
    # Если библиотеки boto3 или google-cloud-secret-manager не установлены,
    # вызов методов этих провайдеров выбросит OptionalDependencyError.

    aws_provider = AWSSecretManagerProvider(region_name="us-east-1")

    # GCP провайдеру можно передать project_id явно или опустить
    # (тогда он попытается прочесть его из GOOGLE_CLOUD_PROJECT)
    gcp_provider = GCPSecretManagerProvider(project_id="my-gcp-project")

    # 2. Создаем SecretManager с цепочкой провайдеров: AWS -> GCP -> Env.
    # Поиск секретов будет выполняться последовательно.
    # Если AWS недоступен или секрет там не найден, поиск перейдет к GCP, затем к Env.
    secrets = SecretManager(
        service_name="my_service", providers=[aws_provider, gcp_provider, EnvProvider()]
    )

    print("\n--- Демонстрация механизма Fallback в цепочке провайдеров ---")

    # Установим локальную переменную окружения для симуляции fallback
    os.environ["DATABASE_URL"] = "postgresql://localhost/db"

    # Попытаемся получить секрет.
    # Так как AWS и GCP у нас в примере не настроены (или выбросят ошибку отсутствия SDK/сетей),
    # SecretManager автоматически залогирует предупреждение о сбое в облаке,
    # перейдет к EnvProvider и успешно найдет секрет там.
    try:
        db_url = secrets.get_secret("DATABASE_URL")
        print(f"Успешно получен секрет: {db_url}")
    except OptionalDependencyError as e:
        print(f"Библиотека для облачного провайдера отсутствует: {e}")
    except Exception as e:
        print(f"Произошла ошибка при работе с цепочкой провайдеров: {e}")

    print("\n--- Как сохранить секрет в конкретное облако ---")
    print(
        "При вызове `secrets.save_secret('my_key', 'my_val')` SecretManager "
        "попытается записать секрет в первый провайдер в цепочке, поддерживающий запись."
    )
    print("Вы также можете использовать провайдеры напрямую:")

    # Прямое использование провайдера
    try:
        # Для AWS:
        # aws_provider.set("API_KEY", "super_secret", "my_service")
        # val = aws_provider.get("API_KEY", "my_service")
        # print(f"Получено значение напрямую: {val}")
        pass
    except OptionalDependencyError:
        print("Для работы примера установите зависимости: pip install chutils[aws,gcp]")


if __name__ == "__main__":
    main()
