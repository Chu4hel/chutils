"""
Пример 8: Настройка нескольких независимых логгеров.

Этот пример показывает, как настроить несколько логгеров с разными 
параметрами (уровни, файлы, типы ротации), используя разные секции в config.yml.
"""

from chutils.logger import setup_logger, ChutilsLogger


def main() -> None:
    """
    Создает логгеры, обращаясь к разным секциям конфигурационного файла.
    """
    # 1. Логгер 'main' - использует стандартную секцию [Logging] из config.yml.
    main_logger: ChutilsLogger = setup_logger("main")
    main_logger.info("Это сообщение от ОСНОВНОГО логгера.")

    # 2. Логгер 'audit' - использует настройки из секции [AuditLogger].
    # Там может быть указан другой файл (например, 'audit.log') и другой уровень.
    audit_logger: ChutilsLogger = setup_logger("audit", config_section_name="AuditLogger")
    audit_logger.debug("Это DEBUG-сообщение от логгера АУДИТА.")

    # 3. Логгер 'events' - использует секцию [EventLogger].
    # В примере config.yml для него настроена ротация по времени, а не по размеру.
    event_logger: ChutilsLogger = setup_logger("events", config_section_name="EventLogger")
    event_logger.info("Логгер СОБЫТИЙ работает (настроен через EventLogger).")

    print("\n[OK] Логирование выполнено в разные потоки.")
    print("Загляните в папку 'logs/', чтобы увидеть раздельные файлы для каждого логгера.")


if __name__ == "__main__":
    main()
