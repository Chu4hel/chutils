"""
Модуль для настройки логирования.

Предоставляет унифицированную функцию setup_logger для создания и настройки логгеров,
которые могут выводить сообщения в консоль и в файлы с автоматической ротацией.
Директория для логов ('logs') создается автоматически в корне проекта.
"""

import logging
import logging.handlers
import os
from typing import Optional

# Импортируем наш модуль config для доступа к путям и настройкам
from . import config

# --- Пользовательские уровни логирования ---
# Для более гранулярного контроля над отладочными сообщениями.

DEVDEBUG_LEVEL_NUM = 9
DEVDEBUG_LEVEL_NAME = "DEVDEBUG"
MEDIUMDEBUG_LEVEL_NUM = 15
MEDIUMDEBUG_LEVEL_NAME = "MEDIUMDEBUG"

logging.addLevelName(MEDIUMDEBUG_LEVEL_NUM, MEDIUMDEBUG_LEVEL_NAME)
logging.addLevelName(DEVDEBUG_LEVEL_NUM, DEVDEBUG_LEVEL_NAME)


class ChutilsLogger(logging.Logger):
    """
    Кастомный класс логгера, который расширяет стандартный `logging.Logger`.

    Основная цель этого класса — добавить поддержку пользовательских уровней
    логирования (`devdebug` и `mediumdebug`), обеспечивая при этом
    корректную работу статических анализаторов и автодополнения в IDE.

    Вам не нужно создавать экземпляр этого класса напрямую. Используйте
    функцию `setup_logger()`, которая автоматически вернет объект этого типа.

    :Example:
        from chutils.logger import setup_logger, ChutilsLogger

        # Используем наш класс для аннотации типа, чтобы IDE давала подсказки
        logger: ChutilsLogger = setup_logger()

        # Теперь IDE знает об этом методе и не будет показывать предупреждений
        logger.mediumdebug("Это сообщение с автодополнением.")
    """

    def mediumdebug(self, message, *args, **kws):
        """Логирует сообщение с уровнем MEDIUMDEBUG (15)."""
        if self.isEnabledFor(MEDIUMDEBUG_LEVEL_NUM):
            self._log(MEDIUMDEBUG_LEVEL_NUM, message, args, **kws)

    def devdebug(self, message, *args, **kws):
        """Логирует сообщение с уровнем DEVDEBUG (9)."""
        if self.isEnabledFor(DEVDEBUG_LEVEL_NUM):
            self._log(DEVDEBUG_LEVEL_NUM, message, args, **kws)


# --- Глобальное состояние для "ленивой" инициализации ---

# Кэш для пути к директории логов. Изначально пуст.
_LOG_DIR: Optional[str] = None
# Глобальный экземпляр основного логгера приложения
_logger_instance: Optional[ChutilsLogger] = None
# Флаг, чтобы сообщение об инициализации выводилось только один раз
_initialization_message_shown = False


def _get_log_dir() -> Optional[str]:
    """
    "Лениво" получает и кэширует путь к директории логов.

    При первом вызове:
    1. Запускает поиск корня проекта через модуль config.
    2. Создает директорию 'logs' в корне проекта, если ее нет.
    3. Кэширует результат.
    При последующих вызовах немедленно возвращает кэшированный путь.
    """
    global _LOG_DIR
    # Если путь уже кэширован, сразу возвращаем его.
    if _LOG_DIR is not None:
        return _LOG_DIR

    # Запускаем инициализацию в config, если она еще не была выполнена.
    # Это "сердце" автоматического обнаружения.
    config._initialize_paths()

    # Берем найденный config'ом базовый каталог проекта.
    base_dir = config._BASE_DIR

    # Если корень проекта не был найден, файловое логирование невозможно.
    if not base_dir:
        print("ПРЕДУПРЕЖДЕНИЕ: Не удалось определить корень проекта, файловое логирование будет отключено.")
        return None

    # Создаем путь к директории логов и саму директорию, если нужно.
    log_path = os.path.join(base_dir, 'logs')
    if not os.path.exists(log_path):
        try:
            os.makedirs(log_path)
            print(f"INFO: Создана директория для логов: {log_path}")
        except OSError as e:
            # Если не удалось создать директорию, логирование в файл будет невозможно.
            print(f"ОШИБКА: Не удалось создать директорию для логов {log_path}: {e}")
            return None

    # Кэшируем успешный результат и возвращаем его.
    _LOG_DIR = log_path
    return _LOG_DIR


def setup_logger(name: str = 'app_logger', log_level_str: str = '') -> ChutilsLogger:
    """
    Настраивает и возвращает логгер с нужным именем.

    - Предотвращает повторную настройку уже существующего логгера.
    - Читает настройки из config.ini (уровень, имя файла и т.д.).
    - Добавляет обработчики для вывода в консоль и в файл с ежедневной ротацией.

    Args:
        name (str): Имя логгера. 'app_logger' используется для основного логгера приложения.
        log_level_str (str, optional): Явное указание уровня логирования (например, 'DEBUG').
                                       Если не задан, берется из конфига.

    Returns:
        logging.Logger: Настроенный экземпляр логгера.
    """
    global _logger_instance, _initialization_message_shown

    # Если логгер с таким именем уже имеет обработчики, значит он настроен.
    # Просто возвращаем его, чтобы не дублировать вывод.
    existing_logger = logging.getLogger(name)
    if existing_logger.hasHandlers():
        return existing_logger  # type: ignore

    # Если запрашивается основной логгер приложения и он уже есть в кэше.
    if name == 'app_logger' and _logger_instance:
        return _logger_instance

    # Получаем директорию для логов. Это первая точка, где запускается вся магия поиска путей.
    log_dir = _get_log_dir()

    # Загружаем конфигурацию для получения настроек логирования.
    cfg = config.get_config()

    # Определяем уровень логирования
    if not log_level_str:
        log_level_str = config.get_config_value('Logging', 'log_level', 'INFO', cfg)
    log_level = getattr(logging, log_level_str.upper(), logging.INFO)

    # Получаем остальные настройки из конфига
    log_file_name = config.get_config_value('Logging', 'log_file_name', 'app.log', cfg)
    backup_count = config.get_config_int('Logging', 'log_backup_count', 3, cfg)

    # Создаем и настраиваем новый экземпляр логгера
    logger = logging.getLogger(name)
    logger.setLevel(log_level)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # 1. Обработчик для вывода в консоль (StreamHandler)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 2. Обработчик для записи в файл (TimedRotatingFileHandler)
    #    Добавляем его, только если директория логов была успешно определена.
    if log_dir and log_file_name:
        log_file_path = os.path.join(log_dir, log_file_name)
        try:
            # Ротация каждый день ('D'), храним backup_count старых файлов
            file_handler = logging.handlers.TimedRotatingFileHandler(
                log_file_path,
                when="D",
                interval=1,
                backupCount=backup_count,
                encoding='utf-8'
            )
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

            # Выводим информационное сообщение только один раз для всего приложения
            if not _initialization_message_shown:
                logger.debug(
                    f"Логирование настроено. Уровень: {log_level_str}. "
                    f"Файл: {log_file_path}, ротация: {backup_count} дней."
                )
                _initialization_message_shown = True
        except Exception as e:
            logger.error(f"Не удалось настроить файловый обработчик логов для {log_file_path}: {e}")
    else:
        if not _initialization_message_shown:
            logger.warning("Директория для логов не настроена. Файловое логирование отключено.")
            _initialization_message_shown = True

    # Кэшируем основной логгер приложения
    if name == 'app_logger':
        _logger_instance = logger

    return logger  # type: ignore
