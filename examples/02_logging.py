# examples/02_logging.py
import os
import logging # Added for logging.INFO
from chutils import setup_logger, ChutilsLogger

# Настраиваем логгер.
# Если в config.yml есть секция [Logging], ее настройки будут использованы.
# В config.yml настроена ротация по размеру (1МБ) со сжатием и 5 бэкапами.
# Логи будут выводиться в консоль и в файл logs/example_app.log
# (папка logs будет создана в корне проекта).
logger: ChutilsLogger = setup_logger("example_logger")

logger.info("Это информационное сообщение из основного логгера.")
logger.debug("Это сообщение для отладки.")
logger.warning("А это - предупреждение.")

# Используем кастомные уровни
logger.mediumdebug("Сообщение со средней детализацией.")
logger.devdebug("Сообщение с максимальной детализацией для разработчика.")

logger.info("--- Демонстрация ротации логов по размеру со сжатием ---")
logger.info("В config.yml для секции [Logging] установлен max_bytes: 1048576 (1МБ) и compress: true.")
logger.info("Будет записано много сообщений, чтобы вызвать ротацию.")
logger.info("После завершения проверьте папку 'logs' в корне проекта.")
logger.info("Вы должны увидеть файлы 'app.log' и несколько 'app.log.N.gz'.")

# Записываем много сообщений, чтобы вызвать ротацию
for i in range(15000): # Количество сообщений, достаточное для превышения 1МБ
    logger.info(f"Это сообщение номер {i}. Оно поможет заполнить лог-файл и вызвать ротацию.")

logger.info("Пример логирования завершен. Проверьте консоль и папку 'logs' в корне проекта.")
logger.info("Вы должны увидеть ротированные и сжатые файлы логов.")


# --- Демонстрация настройки логгеров из разных секций конфига ---
logger.info("\n--- Демонстрация настройки логгеров из разных секций конфига ---")

# Логгер для аудита, настроенный через секцию [AuditLogger] в config.yml
# Эта секция переопределяет настройки из [Logging], например, log_level и log_file_name.
audit_logger: ChutilsLogger = setup_logger(
    "app_audit_logger",
    config_section_name="AuditLogger"
)
audit_logger.info("Это сообщение из аудиторского логгера. Должно быть записано в audit.log.")
audit_logger.debug("Это DEBUG-сообщение из аудиторского логгера. Уровень: INFO, поэтому оно не появится.")

# Логгер для событий, настроенный через секцию [EventLogger] в config.yml
# Здесь могут быть специфичные настройки, например, ротация по времени, а не по размеру.
event_logger: ChutilsLogger = setup_logger(
    "app_event_logger",
    config_section_name="EventLogger"
)
event_logger.info("Это сообщение из логгера событий. Должно быть записано в events.log.")
event_logger.warning("Это предупреждение из логгера событий.")

logger.info("Примеры логгеров с кастомными секциями завершены.")

