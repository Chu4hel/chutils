"""
Пример использования pytest-фикстур chutils для тестирования приложений.

Этот файл демонстрирует, как фикстуры `mock_chutils_config`, `mock_chutils_secrets` 
и `capture_chutils_logs` упрощают написание тестов для кода, использующего chutils.

Для запуска этого примера как теста выполните:
    pytest examples/25_testing_fixtures_example.py
"""

from chutils import get_config_value, setup_logger, SecretManager, bind_context

# Чтобы фикстуры были доступны, их нужно импортировать явно или через pytest_plugins
from chutils.testing.fixtures import (
    mock_chutils_config,
    mock_chutils_secrets,
    capture_chutils_logs,
)


def my_business_logic():
    """Пример бизнес-логики, которую мы будем тестировать."""
    logger = setup_logger("business")

    # 1. Читаем конфиг
    app_mode = get_config_value("app", "mode", fallback="production")
    logger.info(f"Запуск в режиме: {app_mode}")

    # 2. Получаем секрет
    sm = SecretManager(service_name="my_app")
    api_key = sm.get_secret("api_key")

    if not api_key:
        logger.error("API ключ не найден!")
        return False

    # 3. Логируем с контекстом
    with bind_context(user_id=123):
        logger.info("Выполнение важной операции")

    return True


def test_business_logic_success(mock_chutils_config, mock_chutils_secrets, capture_chutils_logs):
    """Тест успешного сценария с использованием всех фикстур."""

    # Настраиваем фейковый конфиг
    mock_chutils_config.set("app", "mode", "testing")

    # Настраиваем фейковый секрет
    mock_chutils_secrets.set_secret("api_key", "fake-dev-token")

    # Запускаем логику
    result = my_business_logic()

    # Проверяем результат
    assert result is True

    # Проверяем логи
    assert capture_chutils_logs.has_message("Запуск в режиме: testing")
    assert capture_chutils_logs.has_message("Выполнение важной операции")

    # Проверяем наличие контекста в логах
    records = capture_chutils_logs.get_by_field("user_id", 123)
    assert len(records) == 1
    assert "важной операции" in records[0].getMessage()


def test_business_logic_missing_secret(mock_chutils_config, mock_chutils_secrets, capture_chutils_logs):
    """Тест сценария, когда секрет отсутствует."""

    # Секрет НЕ устанавливаем
    result = my_business_logic()

    assert result is False
    assert capture_chutils_logs.has_message("API ключ не найден!")


if __name__ == "__main__":
    print("Этот файл предназначен для запуска через pytest:")
    print("    pytest examples/25_testing_fixtures_example.py")
