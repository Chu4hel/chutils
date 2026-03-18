"""
Пример 4: Комплексное использование всех компонентов.

Этот пример имитирует реальное приложение, которое использует конфигурацию для 
настроек подключения, SecretManager для паролей и логгер для отслеживания работы.
"""

from chutils import get_config_value, setup_logger, SecretManager, ChutilsLogger


def main() -> None:
    """
    Основной сценарий: загрузка конфига -> получение пароля -> имитация работы.
    """
    # 1. Инициализируем логгер (будет использовать настройки из [Logging] в config.yml)
    logger: ChutilsLogger = setup_logger("my_app")
    logger.info("--- Запуск демонстрационного приложения ---")

    # 2. Создаем менеджер секретов (имя сервиса возьмется из конфига)
    secrets = SecretManager()

    # 3. Читаем настройки из конфигурации
    db_host: str = get_config_value("Database", "host", fallback="localhost")
    db_user: str = get_config_value("Database", "user", fallback="admin")

    logger.info("Конфигурация загружена для хоста: %s", db_host)

    # 4. Пытаемся получить пароль пользователя из безопасного хранилища
    password_key = f"{db_user}_password"
    db_password: str = secrets.get_secret(password_key)

    if not db_password:
        logger.warning("Пароль для '%s' не найден в Keyring. Сохраняем тестовое значение...", db_user)
        # В реальной жизни здесь могла бы быть форма ввода пароля
        secrets.save_secret(password_key, "SecurePassword_999")
        db_password = secrets.get_secret(password_key)

    # 5. Имитируем бизнес-логику (например, подключение к базе)
    logger.info("Подключение к БД...")
    if db_password:
        logger.info("[SUCCESS] Успешная авторизация пользователя '%s' на %s.", db_user, db_host)
    else:
        logger.error("[FAILED] Не удалось получить учетные данные!")

    logger.info("--- Завершение работы примера ---")


if __name__ == "__main__":
    main()
