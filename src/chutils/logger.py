"""
Модуль для настройки логирования.

Предоставляет унифицированную функцию setup_logger для создания и настройки логгеров,
которые могут выводить сообщения в консоль и в файлы с автоматической ротацией.
Директория для логов ('logs') создается автоматически в корне проекта.
"""

import logging
import logging.handlers
import os
from enum import Enum
from pathlib import Path
from typing import Optional, Any

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


class LogLevel(str, Enum):
    """Перечисление для уровней логирования."""
    DEVDEBUG = "DEVDEBUG"
    DEBUG = "DEBUG"
    MEDIUMDEBUG = "MEDIUMDEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class SafeTimedRotatingFileHandler(logging.handlers.TimedRotatingFileHandler):
    """
    Надежный обработчик ротации логов, особенно для Windows.

    Этот класс решает проблему `PermissionError` при ротации логов в Windows,
    гарантируя, что файл будет закрыт перед переименованием.
    Он явно закрывает файловый поток перед вызовом стандартной логики ротации.
    """

    def doRollover(self):
        if self.stream:
            self.stream.close()
            self.stream = None
        super().doRollover()


class CompressingRotatingFileHandler(logging.handlers.RotatingFileHandler):
    """
    Обработчик ротации по размеру с поддержкой сжатия, который корректно
    обрабатывает существующие сжатые бэкапы.
    """

    def doRollover(self):
        """
        Выполняет ротацию логов:
        1. Сдвигает существующие архивы (`log.1.gz` -> `log.2.gz`).
        2. Переименовывает текущий лог в `log.1`.
        3. Открывает новый пустой лог-файл для дальнейшей записи.
        4. Сжимает `log.1` в `log.1.gz` и удаляет `log.1`.
        """
        # Закрываем текущий поток
        if self.stream:
            self.stream.close()
            self.stream = None

        # 1. Сдвигаем существующие сжатые бэкапы
        if self.backupCount > 0:
            for i in range(self.backupCount - 1, 0, -1):
                sfn_gz = f"{self.baseFilename}.{i}.gz"
                dfn_gz = f"{self.baseFilename}.{i + 1}.gz"
                if os.path.exists(sfn_gz):
                    if os.path.exists(dfn_gz):
                        os.remove(dfn_gz)
                    os.rename(sfn_gz, dfn_gz)

        # 2. Ротируем текущий лог-файл в `basename.1`
        dfn_uncompressed = f"{self.baseFilename}.1"
        if os.path.exists(dfn_uncompressed):
            os.remove(dfn_uncompressed)

        dfn_compressed = f"{dfn_uncompressed}.gz"
        if os.path.exists(dfn_compressed):
            os.remove(dfn_compressed)

        if os.path.exists(self.baseFilename):
            os.rename(self.baseFilename, dfn_uncompressed)

        # 3. Открываем новый поток (создает новый пустой лог-файл)
        self.stream = self._open()

        # 4. Сжимаем новый бэкап `basename.1`
        if os.path.exists(dfn_uncompressed):
            try:
                import gzip
                with open(dfn_uncompressed, 'rb') as f_in:
                    with gzip.open(dfn_compressed, 'wb') as f_out:
                        f_out.writelines(f_in)

                import sys
                if sys.platform == "win32":
                    try:
                        import ctypes
                        ctypes.windll.kernel32.DeleteFileW(dfn_uncompressed)
                    except (ImportError, AttributeError):
                        os.remove(dfn_uncompressed)
                else:
                    os.remove(dfn_uncompressed)
            except Exception as e:
                self.handleError(f"Ошибка при сжатии или удалении {dfn_uncompressed}: {e}")


class CompressingTimedRotatingFileHandler(SafeTimedRotatingFileHandler):
    """
    Обработчик ротации по времени с поддержкой сжатия.
    """

    def doRollover(self):
        """
        Выполняет ротацию и сжимает все старые лог-файлы.
        """
        # Вызываем стандартный doRollover, который переименует файлы
        super().doRollover()

        # Получаем список всех ротированных файлов, которые знает обработчик
        # Этот метод идеально подходит, так как он возвращает именно те файлы,
        # которые являются бэкапами.
        files_to_compress = self.getFilesToDelete()

        for source_file in files_to_compress:
            dest_file = f"{source_file}.gz"

            # Если исходный файл существует и сжатого еще нет
            if os.path.exists(source_file) and not os.path.exists(dest_file):
                try:
                    import gzip
                    with open(source_file, 'rb') as f_in:
                        with gzip.open(dest_file, 'wb') as f_out:
                            f_out.writelines(f_in)
                    os.remove(source_file)  # Удаляем исходный несжатый файл
                except Exception as e:
                    self.handleError(f"Ошибка при сжатии файла {source_file}: {e}")


class ChutilsLogger(logging.Logger):
    """
    Кастомный класс логгера, который расширяет стандартный `logging.Logger`.

    Добавляет поддержку пользовательских уровней логирования (`devdebug` и `mediumdebug`),
    обеспечивая при этом корректную работу статических анализаторов и автодополнения в IDE.

    Иерархия уровней:
        - `DEVDEBUG` (9): Максимально подробный вывод для глубокой отладки.
          Предназначен для вывода дампов переменных, внутренних состояний и т.д.
        - `DEBUG` (10): Стандартный отладочный уровень.
        - `MEDIUMDEBUG` (15): Промежуточный уровень между DEBUG и INFO.
          Полезен для менее критичной, но более подробной, чем INFO, информации.
        - `INFO` (20): Стандартный информационный уровень.

    Note:
        Вам не нужно создавать экземпляр этого класса напрямую. Используйте
        функцию `setup_logger()`, которая автоматически вернет объект этого типа.

    Example:
        ```python
        from chutils.logger import setup_logger, ChutilsLogger

        # Используем наш класс для аннотации типа, чтобы IDE давала подсказки
        logger: ChutilsLogger = setup_logger()

        # Теперь IDE знает об этом методе и не будет показывать предупреждений
        logger.mediumdebug("Это сообщение с автодополнением.")
        ```
    """

    def mediumdebug(self, message: str, *args: Any, **kws: Any):
        """
        Логирует сообщение с уровнем MEDIUMDEBUG (15).

        Args:
            message: Сообщение для логирования.
            *args: Аргументы для форматирования сообщения.
            **kws: Ключевые слова для `_log`.
        """
        if self.isEnabledFor(MEDIUMDEBUG_LEVEL_NUM):
            self._log(MEDIUMDEBUG_LEVEL_NUM, message, args, **kws)

    def devdebug(self, message: str, *args: Any, **kws: Any):
        """
        Логирует сообщение с уровнем DEVDEBUG (9).

        Args:
            message: Сообщение для логирования.
            *args: Аргументы для форматирования сообщения.
            **kws: Ключевые слова для `_log`.
        """
        if self.isEnabledFor(DEVDEBUG_LEVEL_NUM):
            self._log(DEVDEBUG_LEVEL_NUM, message, args, **kws)


logging.setLoggerClass(ChutilsLogger)

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

    Returns:
        str: Путь к директории логов.
        None (None): Если корень проекта не найден.
    """
    global _LOG_DIR
    logging.debug("Вызов _get_log_dir(). Текущее _LOG_DIR: %s", _LOG_DIR)
    # Если путь уже кэширован, сразу возвращаем его.
    if _LOG_DIR is not None:
        return _LOG_DIR

    # Запускаем инициализацию в config, если она еще не была выполнена.
    # Это "сердце" автоматического обнаружения.
    config._initialize_paths()

    # Берем найденный config'ом базовый каталог проекта.
    base_dir = config._BASE_DIR
    logging.debug("В _get_log_dir() определен base_dir: %s", base_dir)

    # Если корень проекта не был найден, файловое логирование невозможно.
    if not base_dir:
        logging.warning("ПРЕДУПРЕЖДЕНИЕ: Не удалось определить корень проекта, файловое логирование будет отключено.")
        return None

    # Создаем путь к директории логов и саму директорию, если нужно.
    log_path = Path(base_dir) / 'logs'
    logging.debug("В _get_log_dir() определен log_path: %s", log_path)
    if not log_path.exists():
        try:
            log_path.mkdir(parents=True, exist_ok=True)
            logging.info("Создана директория для логов: %s", log_path)
        except OSError as e:
            # Если не удалось создать директорию, логирование в файл будет невозможно.
            logging.error("Не удалось создать директорию для логов %s: %s", log_path, e)
            return None

    # Кэшируем успешный результат и возвращаем его.
    _LOG_DIR = str(log_path)
    logging.debug("В _get_log_dir() кэширован _LOG_DIR: %s", _LOG_DIR)
    return _LOG_DIR


def setup_logger(
        name: str = 'app_logger',
        log_level: Optional[LogLevel] = None,
        log_file_name: Optional[str] = None,
        force_reconfigure: bool = False,
        rotation_type: str = 'time',
        max_bytes: int = 0,
        compress: bool = False,
        backup_count: int = 3
) -> ChutilsLogger:
    """
    Настраивает и возвращает логгер с нужным именем.

    Функция идемпотентна: она предотвращает повторную настройку уже
    существующего логгера. Настройки (уровень, имя файла и т.д.) читаются
    из конфигурационного файла. По умолчанию добавляются обработчики для
    вывода в консоль и в файл с ежедневной ротацией.

    Args:
        name: Имя логгера. `app_logger` используется для основного логгера
            приложения и его экземпляр кэшируется.
        log_level: Явное указание уровня логирования. Если не задан,
            значение берется из конфигурационного файла, а если и там нет -
            используется 'INFO'.
        log_file_name: Опциональное имя файла для логирования. Если указано,
            логгер будет писать в этот файл. Если не указано, имя файла
            берется из конфигурационного файла ('Logging', 'log_file_name').
        force_reconfigure: Если True, принудительно удаляет все существующие
                           обработчики и настраивает логгер заново.
        rotation_type: Тип ротации логов. Может быть 'time' (по умолчанию, ежедневная)
                       или 'size' (по размеру файла).
        max_bytes: Максимальный размер файла лога в байтах перед ротацией,
                   если `rotation_type` установлен в 'size'. По умолчанию 0 (без лимита).
        compress: Если True, ротированные файлы логов будут сжиматься в формат .gz.
                  По умолчанию False.
        backup_count: Количество хранимых ротированных файлов логов.
                      Старые файлы будут удаляться. По умолчанию 3.

    Returns:
       logging.Logger: Настроенный экземпляр ChutilsLogger.
    """
    global _logger_instance, _initialization_message_shown
    logging.debug(
        "Вызов setup_logger() для логгера '%s'. log_file_name: %s, force_reconfigure: %s",
        name,
        log_file_name,
        force_reconfigure
    )

    # Если логгер с таким именем уже имеет обработчики, значит он настроен.
    # Просто возвращаем его, чтобы не дублировать вывод.
    existing_logger = logging.getLogger(name)
    if existing_logger.hasHandlers() and not force_reconfigure:
        logging.debug("Логгер '%s' уже настроен, возвращаем существующий экземпляр.", name)
        return existing_logger  # type: ignore

    # Если требуется принудительная перенастройка, очищаем старые обработчики
    if force_reconfigure:
        logging.debug("Принудительная перенастройка для '%s'. Удаление старых обработчиков...", name)
        for handler in existing_logger.handlers[:]:
            handler.close()  # Закрываем файлы, если они были открыты
            existing_logger.removeHandler(handler)

    # Если запрашивается основной логгер приложения и он уже есть в кэше.
    if name == 'app_logger' and _logger_instance:
        logging.debug("Возвращаем кэшированный основной логгер.")
        return _logger_instance

    # Получаем директорию для логов. Это первая точка, где запускается вся магия поиска путей.
    log_dir = _get_log_dir()
    logging.debug("setup_logger() получил log_dir: %s", log_dir)

    # Загружаем конфигурацию для получения настроек логирования.
    cfg = config.get_config()

    # Определяем уровень логирования
    if isinstance(log_level, str):
        try:
            log_level_enum = LogLevel(log_level.upper())
        except ValueError:
            log_level_enum = LogLevel.INFO
    elif log_level is None:
        level_from_config = config.get_config_value('Logging', 'log_level', 'INFO', cfg)
        try:
            log_level_enum = LogLevel(level_from_config.upper())
        except ValueError:
            log_level_enum = LogLevel.INFO
    else:
        log_level_enum = log_level

    level_int = getattr(logging, log_level_enum.value, logging.INFO)
    existing_logger.setLevel(level_int)
    logging.debug("Уровень логирования для '%s' установлен на: %s (%s)", name, log_level_enum.value, level_int)

    # Определяем имя файла лога
    if log_file_name is None:
        log_file_name = config.get_config_value('Logging', 'log_file_name', 'app.log', cfg)
    logging.debug("Имя файла лога для '%s' определено как: %s", name, log_file_name)

    # Определяем параметры ротации
    rotation_type = config.get_config_value('Logging', 'rotation_type', rotation_type, cfg)
    max_bytes = config.get_config_int('Logging', 'max_bytes', max_bytes, cfg)
    compress = config.get_config_boolean('Logging', 'compress', compress, cfg)
    backup_count = config.get_config_int('Logging', 'log_backup_count', 3, cfg)

    # Создаем и настраиваем новый экземпляр логгера
    logger = existing_logger
    logger.setLevel(level_int)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Обработчик для вывода в консоль (StreamHandler)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Обработчик для записи в файл (TimedRotatingFileHandler)
    # Добавляем его, только если директория логов была успешно определена.
    if log_dir and log_file_name:
        # ЕСЛИ ПУТЬ ПЕРЕДАН ЯВНО И ОН АБСОЛЮТНЫЙ, ИСПОЛЬЗУЕМ ЕГО
        # Это нужно для нашего отладочного теста, который работает во временной папке
        if Path(log_file_name).is_absolute():
            log_file_path = Path(log_file_name)
        else:
            log_file_path = Path(log_dir) / log_file_name
        logging.debug("Попытка настроить файловый обработчик для %s в %s", name, log_file_path)
        try:
            file_handler: Optional[logging.FileHandler] = None
            if rotation_type == 'size':
                handler_class = CompressingRotatingFileHandler if compress else logging.handlers.RotatingFileHandler
                file_handler = handler_class(
                    log_file_path,
                    maxBytes=max_bytes,
                    backupCount=backup_count,
                    encoding='utf-8'
                )
            else:  # 'time'
                handler_class = CompressingTimedRotatingFileHandler if compress else SafeTimedRotatingFileHandler
                file_handler = handler_class(
                    log_file_path,
                    when="D",
                    interval=1,
                    backupCount=backup_count,
                    encoding='utf-8'
                )

            if file_handler:
                file_handler.setFormatter(formatter)
                logger.addHandler(file_handler)

                if not _initialization_message_shown:
                    logger.debug(
                        "Логирование настроено. Уровень: %s. Файл: %s, ротация: %s, сжатие: %s.",
                        log_level.value, log_file_path, rotation_type, compress
                    )
                    _initialization_message_shown = True
        except Exception as e:
            logger.error("Не удалось настроить файловый обработчик логов для %s: %s", log_file_path, e)
    else:
        if not _initialization_message_shown:
            logger.warning("Директория для логов не настроена. Файловое логирование отключено.")
            _initialization_message_shown = True

    # Кэшируем основной логгер приложения
    if name == 'app_logger':
        _logger_instance = logger

    return logger  # type: ignore
