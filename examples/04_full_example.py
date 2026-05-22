"""
Пример 4: Комплексное использование всех компонентов.

Этот пример имитирует реальное приложение, которое использует конфигурацию для 
настроек подключения, SecretManager для паролей, логгер для отслеживания работы
и OpenTelemetry для трассировки вызовов.
"""

from chutils import get_config_value, setup_logger, SecretManager, ChutilsLogger, setup_tracing, trace


@trace(capture_kwargs=True)
def connect_to_db(host: str, user: str, password: str) -> bool:
    """Имитация подключения к БД с трассировкой."""
    logger = setup_logger("my_app")
    logger.info("Подключение к БД...")

    if password:
        logger.info("[SUCCESS] Успешная авторизация пользователя '%s' на %s.", user, host)
        return True

    logger.error("[FAILED] Не удалось получить учетные данные!")
    return False


def main() -> None:
    """
    Основной сценарий: загрузка конфига -> получение пароля -> имитация работы.
    """
    # 1. Настраиваем трассировку (вывод в консоль для примера)
    setup_tracing(service_name="full-demo-app", exporter_type="console")

    # 2. Инициализируем логгер (будет использовать настройки из [Logging] в config.yml)
    # Т.к. мы включили tracing, в логах появятся trace_id и span_id.
    logger: ChutilsLogger = setup_logger("my_app")
    logger.info("--- Запуск демонстрационного приложения ---")

    # 3. Создаем менеджер секретов (имя сервиса возьмется из конфига)
    secrets = SecretManager()

    # 4. Читаем настройки из конфигурации
    db_host: str = get_config_value("Database", "host", fallback="localhost")
    db_user: str = get_config_value("Database", "user", fallback="admin")

    logger.info("Конфигурация загружена для хоста: %s", db_host)

    # 5. Пытаемся получить пароль пользователя из безопасного хранилища
    password_key = f"{db_user}_password"
    db_password: str = secrets.get_secret(password_key)

    if not db_password:
        logger.warning("Пароль для '%s' не найден в Keyring. Сохраняем тестовое значение...", db_user)
        # В реальной жизни здесь могла бы быть форма ввода пароля
        secrets.save_secret(password_key, "SecurePassword_999")
        db_password = secrets.get_secret(password_key)

    # 6. Выполняем "бизнес-логику" (функция обернута в @trace)
    # Обратите внимание: лог внутри connect_to_db будет иметь тот же trace_id, 
    # что и логи в main(), если они вызваны внутри одного спана.
    connect_to_db(db_host, db_user, db_password)

    logger.info("--- Завершение работы примера ---")


if __name__ == "__main__":
    main()
