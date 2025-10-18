# examples/04_full_example.py
from chutils import get_config_value, setup_logger, SecretManager, ChutilsLogger

# 1. Настраиваем логгер.
logger: ChutilsLogger = setup_logger()

# 2. Инициализируем менеджер секретов.
secrets = SecretManager("my_awesome_app")


def setup_credentials():
    """Функция для первоначального сохранения пароля, если его нет."""
    db_user = get_config_value("Database", "user")
    password_key = f"{db_user}_password"

    if not secrets.get_secret(password_key):
        logger.info("Пароль для БД не найден. Сохраняем новый...")
        secrets.save_secret(password_key, "MySuperSecretDbPassword123!")
        logger.info("Пароль для БД сохранен в системном хранилище.")


def connect_to_db():
    """Пример подключения к БД с использованием конфига и секретов."""
    db_host = get_config_value("Database", "host")
    db_user = get_config_value("Database", "user")
    db_password = secrets.get_secret(f"{db_user}_password")

    if not db_password:
        logger.error("Не удалось получить пароль для БД!")
        return

    logger.info(f"Подключаемся к {db_host} от имени {db_user}...")
    # ... логика подключения ...
    logger.info("Успешно подключились!")


def main():
    logger.info("Приложение запущено.")
    setup_credentials()
    connect_to_db()
    logger.info("Приложение завершило работу.")


if __name__ == "__main__":
    main()
