import logging
import logging.handlers
import os
from . import config

PROJECT_ROOT = config.get_base_dir()
LOG_DIR = os.path.join(PROJECT_ROOT, 'logs')
DEVDEBUG_LEVEL_NUM = 9
DEVDEBUG_LEVEL_NAME = "DEVDEBUG"
MEDIUMDEBUG_LEVEL_NUM = 15
MEDIUMDEBUG_LEVEL_NAME = "MEDIUMDEBUG"

logging.addLevelName(MEDIUMDEBUG_LEVEL_NUM, MEDIUMDEBUG_LEVEL_NAME)
logging.addLevelName(DEVDEBUG_LEVEL_NUM, DEVDEBUG_LEVEL_NAME)


def mediumdebug(self, message, *args, **kws):
    # Проверяем, должен ли логгер обрабатывать сообщения этого уровня
    if self.isEnabledFor(MEDIUMDEBUG_LEVEL_NUM):
        # Да, logger takes its '*args' as 'args'.
        self._log(MEDIUMDEBUG_LEVEL_NUM, message, args, **kws)


def devdebug(self, message, *args, **kws):
    # Проверяем, должен ли логгер обрабатывать сообщения этого уровня
    if self.isEnabledFor(DEVDEBUG_LEVEL_NUM):
        # Да, logger takes its '*args' as 'args'.
        self._log(DEVDEBUG_LEVEL_NUM, message, args, **kws)


if not hasattr(logging.Logger, MEDIUMDEBUG_LEVEL_NAME.lower()):
    logging.Logger.mediumdebug = mediumdebug

if not hasattr(logging.Logger, DEVDEBUG_LEVEL_NAME.lower()):
    logging.Logger.devdebug = devdebug

# Убедимся, что директория для логов существует
if not os.path.exists(LOG_DIR):
    try:
        os.makedirs(LOG_DIR)
    except OSError as e:
        # В крайнем случае, если не удалось создать папку, логируем в консоль
        print(f"Не удалось создать директорию для логов {LOG_DIR}: {e}. Логирование будет в консоль.")
        LOG_DIR = None  # Сбрасываем, чтобы обработчик файла не создавался

# Глобальная переменная для хранения инициализированного логгера
_logger_instance = None
MSG = False


def setup_logger(name='app_logger', log_level_str: str = ''):
    """
    Настраивает и возвращает логгер.
    Если логгер с таким именем уже настроен, возвращает его.
    """
    global _logger_instance

    # Проверяем, был ли уже инициализирован логгер с таким именем (или наш основной)
    existing_logger = logging.getLogger(name)
    if existing_logger.hasHandlers():
        return existing_logger  # Возвращаем уже настроенный логгер

    # Если используем наш глобальный экземпляр для основного логгера приложения
    if name == 'app_logger' and _logger_instance:
        return _logger_instance

    cfg = config.get_config()

    if not log_level_str: log_level_str = config.get_config_value('Logging', 'log_level', 'INFO', cfg)
    log_level = getattr(logging, log_level_str.upper(), logging.INFO)

    log_file_name = config.get_config_value('Logging', 'log_file_name', 'app.log', cfg)
    backup_count = config.get_config_int('Logging', 'log_backup_count', 3, cfg)

    logger = logging.getLogger(name)
    logger.setLevel(log_level)

    # Форматтер
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Обработчик для консоли (опционально, но полезно для отладки)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Обработчик для файла с ротацией, если LOG_DIR был успешно создан
    if LOG_DIR and log_file_name:
        log_file_path = os.path.join(LOG_DIR, log_file_name)
        try:
            # Ротация каждый день (D), храним backup_count старых логов
            file_handler = logging.handlers.TimedRotatingFileHandler(
                log_file_path,
                when="D",  # Ежедневная ротация
                interval=1,
                backupCount=backup_count,
                encoding='utf-8'
            )
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
            global MSG
            if not MSG:
                logger.info(
                    f"Логирование настроено. Файл: {log_file_path}, Уровень: {log_level_str}, Ротация: {backup_count} дней.")
                MSG = True
        except Exception as e:
            logger.error(f"Не удалось настроить файловый обработчик логов для {log_file_path}: {e}")
            print(
                f"Ошибка настройки файлового логгера: {e}")  # Дополнительный вывод, т.к. логгер мог не инициализироваться
    else:
        logger.warning("Директория для логов не настроена или не удалось ее создать. Файловое логирование отключено.")

    if name == 'app_logger':
        _logger_instance = logger

    return logger
