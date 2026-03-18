"""
Пример 2: Основы логирования и ротация файлов.

Демонстрирует создание логгера с использованием ChutilsLogger, работу с 
кастомными уровнями (DEVDEBUG, MEDIUMDEBUG) и автоматическую ротацию файлов.
"""

from chutils import setup_logger, ChutilsLogger


def main() -> None:
    """
    Демонстрирует использование различных уровней логирования и ротации.
    """
    # Инициализация логгера. Настройки берутся из секции [Logging] в config.yml.
    # В нашем примере config.yml настроена ротация по размеру (1МБ) со сжатием.
    logger: ChutilsLogger = setup_logger("example_logger")

    logger.info("Это информационное сообщение.")
    logger.warning("Это предупреждение.")
    logger.error("Это сообщение об ошибке.")

    # Кастомные уровни для глубокой отладки.
    # Чтобы увидеть эти сообщения в консоли, установите log_level: DEVDEBUG в config.yml.
    logger.debug("Стандартная отладка (DEBUG).")
    logger.mediumdebug("Отладка средней детализации (MEDIUMDEBUG, уровень 15).")
    logger.devdebug("Максимально детальная отладка (DEVDEBUG, уровень 9).")

    logger.info("\n--- Демонстрация ротации логов ---")
    logger.info("В config.yml для секции [Logging] установлен max_bytes: 1МБ и compress: true.")
    logger.info("При превышении размера файл 'example_app.log' будет сжат в '.gz',")
    logger.info("а новые записи продолжатся в свежем файле.")

    # Записываем несколько сообщений для примера
    for i in range(100):
        logger.devdebug(f"Тестовая запись для заполнения лога #{i}")

    print("\n[OK] Логирование выполнено.")
    print("Проверьте папку 'logs/' в корне вашего проекта.")
    print("Там вы найдете 'example_app.log' и, если данных было много, архивы '.gz'.")


if __name__ == "__main__":
    main()
