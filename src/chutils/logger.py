"""
Модуль для настройки логирования.

Предоставляет унифицированную функцию setup_logger для создания и настройки логгеров,
которые могут выводить сообщения в консоль и в файлы с автоматической ротацией.
Директория для логов ('logs') создается автоматически в корне проекта.
"""

import datetime
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
# Кэш для файловых обработчиков, чтобы избежать конфликтов при ротации.
_file_handler_cache: dict[str, logging.FileHandler] = {}
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
        config_section_name: Optional[str] = None,
        log_level: Optional[LogLevel] = None,
        log_file_name: Optional[str] = None,
        force_reconfigure: bool = False,
        rotation_type: Optional[str] = None,
        max_bytes: Optional[int] = None,
        compress: Optional[bool] = None,
        backup_count: Optional[int] = None,
        encoding: Optional[str] = None,
        when: Optional[str] = None,
        interval: Optional[int] = None,
        utc: Optional[bool] = None,
        at_time: Optional[datetime.time] = None,
        **kwargs: Any
) -> ChutilsLogger:
    """
    Настраивает и возвращает логгер с гибким приоритетом конфигурации.

    Приоритет настроек:
    1. Явные аргументы, переданные в эту функцию.
    2. Объединенные настройки из `Logging.loggers.{name}` (если есть) поверх `Logging.default` (если есть).
    3. Для обратной совместимости: если `Logging.default` и `Logging.loggers` отсутствуют,
       используются прямые настройки из `Logging` (как в старом формате).
    4. Значения по умолчанию, зашитые в коде.

    Args:
        name: Имя логгера. `app_logger` используется как стандартное имя.
        config_section_name: Имя специфичной секции в конфиге (например, 'MyAuditLogger').
            Если указана, настройки из этой секции переопределяют настройки из общей секции `[Logging]`.
            Если не указана, используется только общая секция `[Logging]`.
        log_level: Явное указание уровня логирования (строкой или LogLevel).
                   Если не задан, значение берется из конфигурационного файла.
        log_file_name: Имя файла для логирования. Если не указано, имя берется
                       из конфигурации ('Logging', 'log_file_name').
        force_reconfigure: Если True, принудительно удаляет все существующие
                           обработчики и настраивает логгер заново.
        rotation_type: Тип ротации: 'time' или 'size'.
        max_bytes: Максимальный размер файла для ротации по 'size'.
        compress: Сжимать ли ротированные логи в .gz.
        backup_count: Количество хранимых ротированных файлов.
        encoding: Кодировка файла (по умолчанию 'utf-8').
        when: Для 'time'. Тип интервала ('S', 'M', 'H', 'D', 'midnight', 'W0'-'W6').
        interval: Для 'time'. Длина интервала.
        utc: Для 'time'. Использовать UTC время.
        at_time: Для 'time'. Время ротации (при when='midnight').

        **kwargs: Дополнительные параметры для FileHandler (например, `delay=True`, `errors='ignore'`, `mode='a'`).

    Returns:
       Настроенный экземпляр ChutilsLogger.
    """
    global _initialization_message_shown
    logger = logging.getLogger(name)
    cfg = config.get_config()

    # --- Определение словаря настроек для данного логгера ---
    # По умолчанию используем секцию [Logging]
    default_settings = cfg.get('Logging', {})

    # Если указана специфичная секция, ее настройки переопределяют дефолтные
    specific_settings = {}
    if config_section_name:
        specific_settings = cfg.get(config_section_name, {})

    final_logger_settings = {**default_settings, **specific_settings}

    # --- 1. Определение и установка уровня логирования ---
    # Приоритет: аргумент функции > настройки из конфига > 'INFO'
    final_log_level_str: str
    if log_level is not None:
        final_log_level_str = log_level.value if isinstance(log_level, LogLevel) else str(log_level).upper()
    else:
        level_val = final_logger_settings.get('log_level', 'INFO')
        final_log_level_str = str(level_val).upper()

    try:
        log_level_enum = LogLevel(final_log_level_str)
        level_int = getattr(logging, log_level_enum.value, logging.INFO)
    except ValueError:
        log_level_enum = LogLevel.INFO
        level_int = logging.INFO

    logger.setLevel(level_int)
    logger.propagate = False
    logging.debug("Уровень логирования для '%s' установлен на: %s (%s)", name, log_level_enum.value, level_int)

    # --- Настройка обработчиков (только при необходимости) ---
    if logger.hasHandlers() and not force_reconfigure:
        logging.debug("Обработчики для логгера '%s' уже настроены. Пропускаем настройку.", name)
        return logger  # type: ignore

    if force_reconfigure:
        logging.debug("Принудительная перенастройка для '%s'. Удаление старых обработчиков...", name)
        for handler in logger.handlers[:]:
            # Если это файловый обработчик, пытаемся удалить его из нашего кэша
            if isinstance(handler, logging.FileHandler):
                # Ключ в нашем кэше - это handler.baseFilename
                if handler.baseFilename in _file_handler_cache:
                    del _file_handler_cache[handler.baseFilename]
                    logging.debug("Удален обработчик для %s из кэша.", handler.baseFilename)
            handler.close()
            logger.removeHandler(handler)

    # --- Определение параметров на основе приоритетов ---
    # Приоритет: аргумент функции > настройки из конфига > жестко заданное значение
    final_log_file_name = log_file_name if log_file_name is not None else final_logger_settings.get('log_file_name',
                                                                                                    'app.log')
    final_rotation_type = rotation_type if rotation_type is not None else final_logger_settings.get('rotation_type',
                                                                                                    'time')

    # Для типизированных значений нужна безопасная обработка
    try:
        max_bytes_from_config = int(final_logger_settings.get('max_bytes', 5 * 1024 * 1024))
    except (ValueError, TypeError):
        max_bytes_from_config = 5 * 1024 * 1024
    final_max_bytes = max_bytes if max_bytes is not None else max_bytes_from_config

    compress_val = final_logger_settings.get('compress', False)
    if isinstance(compress_val, str):
        compress_from_config = compress_val.lower() in ['true', '1', 't', 'y', 'yes']
    else:
        compress_from_config = bool(compress_val)
    final_compress = compress if compress is not None else compress_from_config

    try:
        backup_count_from_config = int(final_logger_settings.get('log_backup_count', 3))
    except (ValueError, TypeError):
        backup_count_from_config = 3
    final_backup_count = backup_count if backup_count is not None else backup_count_from_config

    final_encoding = encoding if encoding is not None else final_logger_settings.get('encoding', 'utf-8')
    final_when = when if when is not None else final_logger_settings.get('when', 'D')

    try:
        interval_from_config = int(final_logger_settings.get('interval', 1))
    except (ValueError, TypeError):
        interval_from_config = 1
    final_interval = interval if interval is not None else interval_from_config

    utc_val = final_logger_settings.get('utc', False)
    if isinstance(utc_val, str):
        utc_from_config = utc_val.lower() in ['true', '1', 't', 'y', 'yes']
    else:
        utc_from_config = bool(utc_val)
    final_utc = utc if utc is not None else utc_from_config

    final_at_time = at_time if at_time is not None else final_logger_settings.get('at_time', None)

    # --- 4. Настройка обработчиков ---
    log_dir = _get_log_dir()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    if log_dir and final_log_file_name:
        log_file_path = Path(final_log_file_name) if Path(
            final_log_file_name).is_absolute() else Path(log_dir) / final_log_file_name

        log_file_path_str = str(log_file_path)

        # Проверяем, есть ли уже обработчик для этого файла в кэше
        if log_file_path_str in _file_handler_cache:
            file_handler = _file_handler_cache[log_file_path_str]
            logger.debug("Используется кэшированный файловый обработчик для %s", log_file_path_str)
        else:
            # Если обработчика нет, создаем новый и добавляем в кэш
            logging.debug("Попытка настроить файловый обработчик для %s в %s", name, log_file_path)
            try:
                file_handler: Optional[logging.FileHandler] = None
                common_kwargs = {
                    'encoding': final_encoding,
                    'backupCount': final_backup_count,
                }
                common_kwargs.update(kwargs)

                if final_rotation_type == 'size':
                    handler_class = CompressingRotatingFileHandler if final_compress else logging.handlers.RotatingFileHandler
                    rotation_kwargs = {'maxBytes': final_max_bytes}
                    final_kwargs = {**common_kwargs, **rotation_kwargs}
                    file_handler = handler_class(log_file_path_str, **final_kwargs)
                else:  # 'time'
                    handler_class = CompressingTimedRotatingFileHandler if final_compress else SafeTimedRotatingFileHandler

                    rotation_kwargs = {
                        'when': final_when,
                        'interval': final_interval,
                        'utc': final_utc,
                    }
                    # `at_time` может быть строкой из конфига, нужно преобразовать
                    if isinstance(final_at_time, str):
                        try:
                            final_at_time = datetime.time.fromisoformat(final_at_time)
                        except (TypeError, ValueError):
                            logger.error(
                                "Неверный формат времени '%s' для 'at_time' в конфиге. Используется None.",
                                final_at_time)
                            final_at_time = None

                    if final_at_time is not None:
                        rotation_kwargs['atTime'] = final_at_time

                    final_kwargs = {**common_kwargs, **rotation_kwargs}

                    file_handler = handler_class(log_file_path_str, **final_kwargs)

                if file_handler:
                    file_handler.setFormatter(formatter)
                    # Добавляем новый обработчик в кэш
                    _file_handler_cache[log_file_path_str] = file_handler
                    logger.debug("Новый файловый обработчик для %s добавлен в кэш.", log_file_path_str)

                    if not _initialization_message_shown:
                        info_msg = "."
                        if final_rotation_type == 'time':
                            info_msg = f", интервал: {final_interval}{final_when}"
                        else:
                            info_msg = f", макс. размер: {final_max_bytes}"
                        logger.debug(
                            "Логирование настроено. Уровень: %s. Файл: %s, ротация: %s, сжатие: %s%s",
                            log_level_enum.value, log_file_path, final_rotation_type, final_compress, info_msg
                        )
                        _initialization_message_shown = True
            except Exception as e:
                logger.error("Не удалось настроить файловый обработчик логов для %s: %s", log_file_path, e)
                file_handler = None

        if file_handler:
            logger.addHandler(file_handler)
    elif not _initialization_message_shown:
        logger.warning("Директория для логов не настроена. Файловое логирование отключено.")
        _initialization_message_shown = True

    return logger  # type: ignore
