# examples/02_logging.py
from chutils import setup_logger, ChutilsLogger

# Настраиваем логгер.
# Он автоматически прочитает секцию [Logging] из config.yml.
# Логи будут выводиться в консоль и в файл logs/example_app.log
# (папка logs будет создана в корне проекта).
logger: ChutilsLogger = setup_logger("example_logger")

logger.info("Это информационное сообщение.")
logger.debug("Это сообщение для отладки.")
logger.warning("А это - предупреждение.")

# Используем кастомные уровни
logger.mediumdebug("Сообщение со средней детализацией.")
logger.devdebug("Сообщение с максимальной детализацией для разработчика.")

logger.info("Пример логирования завершен. Проверьте консоль и папку 'logs' в корне проекта.")
