"""
Ядро системы логирования.
Содержит основной класс логгера и функцию инициализации.
"""

import datetime
import logging
import logging.handlers
import os
from enum import Enum
from pathlib import Path
from typing import Optional, Any

from .formatters import JSON_LOGGER_AVAILABLE, ChutilsJsonFormatter
from .handlers import (
    SafeTimedRotatingFileHandler,
    CompressingRotatingFileHandler,
    CompressingTimedRotatingFileHandler
)
from .masking import SecretMaskingFilter, _GLOBAL_MASKS, _update_mask_re
from .. import config
from ..context import ContextFilter

# --- Пользовательские уровни логирования ---

DEVDEBUG_LEVEL_NUM = 9
DEVDEBUG_LEVEL_NAME = "DEVDEBUG"
MEDIUMDEBUG_LEVEL_NUM = 15
MEDIUMDEBUG_LEVEL_NAME = "MEDIUMDEBUG"

logging.addLevelName(MEDIUMDEBUG_LEVEL_NUM, MEDIUMDEBUG_LEVEL_NAME)
logging.addLevelName(DEVDEBUG_LEVEL_NUM, DEVDEBUG_LEVEL_NAME)


class LogLevel(str, Enum):
    """
    Перечисление для поддерживаемых уровней логирования.
    """
    DEVDEBUG = "DEVDEBUG"
    DEBUG = "DEBUG"
    MEDIUMDEBUG = "MEDIUMDEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class ChutilsLogger(logging.Logger):
    """
    Кастомный класс логгера, расширяющий стандартный `logging.Logger`.

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
        Не создавайте экземпляр напрямую. Используйте `setup_logger()`.

    Example:
        ```python
        logger: ChutilsLogger = setup_logger()
        logger.devdebug("Максимально подробное сообщение")
        ```
    """

    def mediumdebug(self, message: str, *args: Any, **kws: Any):
        """
        Логирует сообщение с уровнем MEDIUMDEBUG (15).

        Args:
            message: Сообщение для логирования.
            *args: Аргументы форматирования.
            **kws: Ключевые слова для логгера.
        """
        if self.isEnabledFor(MEDIUMDEBUG_LEVEL_NUM):
            self._log(MEDIUMDEBUG_LEVEL_NUM, message, args, **kws)

    def devdebug(self, message: str, *args: Any, **kws: Any):
        """
        Логирует сообщение с уровнем DEVDEBUG (9).

        Args:
            message: Сообщение для логирования.
            *args: Аргументы форматирования.
            **kws: Ключевые слова для логгера.
        """
        if self.isEnabledFor(DEVDEBUG_LEVEL_NUM):
            self._log(DEVDEBUG_LEVEL_NUM, message, args, **kws)

    def add_mask(self, value: str):
        """
        Добавляет строку в глобальный список маскируемых секретов.

        Каждая зарегистрированная строка будет заменяться на '***' во всех сообщениях
        всех логгеров chutils.

        Args:
            value: Секретная строка для маскирования.
        """
        if value and isinstance(value, str):
            _GLOBAL_MASKS.add(value)
            _update_mask_re()


logging.setLoggerClass(ChutilsLogger)

# --- Глобальное состояние для "ленивой" инициализации ---

_LOG_DIR: Optional[str] = None
_file_handler_cache: dict[str, logging.FileHandler] = {}
_initialization_message_shown = False


def _get_log_dir() -> Optional[str]:
    """
    "Лениво" получает и кэширует путь к директории логов.

    Создает директорию 'logs' в корне проекта при первом обращении.

    Returns:
        str: Путь к директории логов.
        None (None): Если корень проекта не найден.
    """
    global _LOG_DIR
    if _LOG_DIR is not None:
        return _LOG_DIR

    base_dir = config.get_base_dir()
    if not base_dir:
        logging.warning("Не удалось определить корень проекта, файловое логирование отключено.")
        return None

    log_path = Path(base_dir) / 'logs'
    if not log_path.exists():
        try:
            log_path.mkdir(parents=True, exist_ok=True)
            logging.info("Создана директория для логов: %s", log_path)
        except OSError as e:
            logging.error("Не удалось создать директорию для логов %s: %s", log_path, e)
            return None

    _LOG_DIR = str(log_path)
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
        json_format: Optional[bool] = None,
        **kwargs: Any
) -> ChutilsLogger:
    """
    Настраивает и возвращает экземпляр логгера.

    Функция предлагает гибкую настройку, включая управление уровнями, ротацией и сжатием.
    При каждом вызове для существующего логгера его уровень **всегда обновляется**.

    ### Приоритет настроек:
    0. Переменные окружения `CH_LOG_NO_TIME` и `CH_LOG_NO_FILE` (высший приоритет).
    1. Явные аргументы, переданные в эту функцию (например, `log_level=...`).
    2. Секция, указанная в `config_section_name` (например, `[AuditLogger]`).
    3. Общая секция `[Logging]` в `config.yml`.
    4. Значения по умолчанию, зашитые в коде.

    ### Ротация и сжатие:
    - **По времени (`rotation_type='time'`)**: Ротация ежедневно или по интервалу (параметры `when`, `interval`).
    - **По размеру (`rotation_type='size'`)**: Ротация при достижении `max_bytes`.
    - **Сжатие**: Если `compress=True`, старые логи сжимаются в `.gz`.

    Args:
        name: Имя логгера. `app_logger` по умолчанию.
        config_section_name: Имя секции в конфиге (например, 'MyAuditLogger').
            Если указана, настройки из этой секции переопределяют настройки из общей секции `[Logging]`.
            Если не указана, используется только общая секция `[Logging]`.
        log_level: Уровень логирования (строка или LogLevel).
        log_file_name: Имя файла лога. Если не указано, берется из конфига или 'app.log'.
        force_reconfigure: Если True, пересоздает обработчики (обычно они идемпотентны).
        rotation_type: Тип ротации ('time' или 'size').
        max_bytes: Макс. размер файла (для 'size'). По умолчанию 5 МБ.
        compress: Сжимать ли старые логи в `.gz`. По умолчанию False.
        backup_count: Количество хранимых ротированных файлов. По умолчанию 3.
        encoding: Кодировка файла. По умолчанию 'utf-8'.
        when: Интервал ротации для 'time' (например, 'S', 'M', 'H', 'D', 'midnight', 'W0'-'W6').
        interval: Для 'time'. Кратность интервала.
        utc: Для 'time'. Использовать ли UTC время для имен файлов.
        at_time: Для 'time'. Время ротации (для when='midnight').

        **kwargs: Дополнительные параметры для FileHandler (например, `delay=True`, `errors='ignore'`, `mode='a'`).

    Returns:
        Настроенный экземпляр ChutilsLogger.
    """
    global _initialization_message_shown
    logger = logging.getLogger(name)
    cfg = config.get_config()

    default_settings = cfg.get('Logging', {})
    specific_settings = {}
    if config_section_name:
        specific_settings = cfg.get(config_section_name, {})

    final_logger_settings = {**default_settings, **specific_settings}

    # --- Определение флага JSON формата ---
    env_json_val = os.getenv("CH_LOG_JSON", "").lower()
    if env_json_val:
        final_json_format = env_json_val in ["true", "1", "yes", "y"]
    elif json_format is not None:
        final_json_format = json_format
    else:
        config_json = final_logger_settings.get('json_format', False)
        if isinstance(config_json, str):
            final_json_format = config_json.lower() in ["true", "1", "yes", "y"]
        else:
            final_json_format = bool(config_json)

    # --- 1. Определение и установка уровня логирования ---
    final_log_level_str: str
    if log_level is not None:
        final_log_level_str = log_level.value if isinstance(log_level, LogLevel) else str(log_level).upper()
    else:
        level_val = final_logger_settings.get('log_level', 'INFO')
        final_log_level_str = str(level_val).upper()

    level_int = logging.getLevelName(final_log_level_str)
    if not isinstance(level_int, int):
        logger.warning("Неизвестный уровень логирования: '%s'. Используется INFO.", final_log_level_str)
        level_int = logging.INFO

    logger.setLevel(level_int)
    logger.propagate = False

    if logger.hasHandlers() and not force_reconfigure:
        return logger  # type: ignore

    if force_reconfigure:
        for handler in logger.handlers[:]:
            if isinstance(handler, logging.FileHandler):
                if handler.baseFilename in _file_handler_cache:
                    del _file_handler_cache[handler.baseFilename]
            handler.close()
            logger.removeHandler(handler)

    # --- Параметры ---
    final_log_file_name = log_file_name if log_file_name is not None else final_logger_settings.get('log_file_name',
                                                                                                    'app.log')
    final_rotation_type = rotation_type if rotation_type is not None else final_logger_settings.get('rotation_type',
                                                                                                    'time')

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

    # --- Настройка обработчиков ---
    log_dir = _get_log_dir()

    env_no_time = os.getenv("CH_LOG_NO_TIME", "").lower() in ["true", "1", "yes", "y"]
    env_no_file = os.getenv("CH_LOG_NO_FILE", "").lower() in ["true", "1", "yes", "y"]

    if env_no_time:
        log_format = '%(name)s - %(levelname)s %(context)s- %(message)s'
    else:
        log_format = '%(asctime)s - %(name)s - %(levelname)s %(context)s- %(message)s'

    if final_json_format:
        if JSON_LOGGER_AVAILABLE:
            formatter = ChutilsJsonFormatter('%(asctime)s %(name)s %(levelname)s %(message)s')
        else:
            logger.warning(
                "Запрошен формат JSON, но пакет 'python-json-logger' не установлен. Используется стандартный текстовый формат.")
            formatter = logging.Formatter(log_format)
    else:
        formatter = logging.Formatter(log_format)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(level_int)
    logger.addHandler(console_handler)

    if not env_no_file and log_dir and final_log_file_name:
        log_file_path = Path(final_log_file_name) if Path(final_log_file_name).is_absolute() else Path(
            log_dir) / final_log_file_name
        log_file_path_str = str(log_file_path)

        if log_file_path_str in _file_handler_cache:
            file_handler = _file_handler_cache[log_file_path_str]
        else:
            try:
                file_handler: Optional[logging.FileHandler] = None
                common_kwargs = {'encoding': final_encoding, 'backupCount': final_backup_count}
                common_kwargs.update(kwargs)

                if final_rotation_type == 'size':
                    handler_class = CompressingRotatingFileHandler if final_compress else logging.handlers.RotatingFileHandler
                    rotation_kwargs = {'maxBytes': final_max_bytes}
                    final_kwargs = {**common_kwargs, **rotation_kwargs}
                    file_handler = handler_class(log_file_path_str, **final_kwargs)
                else:  # 'time'
                    handler_class = CompressingTimedRotatingFileHandler if final_compress else SafeTimedRotatingFileHandler
                    rotation_kwargs = {'when': final_when, 'interval': final_interval, 'utc': final_utc}
                    if isinstance(final_at_time, str):
                        try:
                            final_at_time = datetime.time.fromisoformat(final_at_time)
                        except (TypeError, ValueError):
                            final_at_time = None
                    if final_at_time is not None:
                        rotation_kwargs['atTime'] = final_at_time
                    final_kwargs = {**common_kwargs, **rotation_kwargs}
                    file_handler = handler_class(log_file_path_str, **final_kwargs)

                if file_handler:
                    file_handler.setFormatter(formatter)
                    _file_handler_cache[log_file_path_str] = file_handler
                    if not _initialization_message_shown:
                        _initialization_message_shown = True
            except Exception as e:
                logger.error("Не удалось настроить файловый обработчик логов для %s: %s", log_file_path, e)
                file_handler = None

        if file_handler:
            logger.addHandler(file_handler)
    elif not _initialization_message_shown:
        logger.warning("Директория для логов не настроена. Файловое логирование отключено.")
        _initialization_message_shown = True

    # --- Маскирование ---
    mask_patterns = final_logger_settings.get('mask_patterns', [])
    if isinstance(mask_patterns, list):
        for pattern in mask_patterns:
            if not pattern:
                continue
            secret_value = final_logger_settings.get(pattern)
            if secret_value and isinstance(secret_value, str):
                _GLOBAL_MASKS.add(secret_value)
            elif isinstance(pattern, str):
                _GLOBAL_MASKS.add(pattern)

    _update_mask_re()

    if not any(isinstance(f, SecretMaskingFilter) for f in logger.filters):
        logger.addFilter(SecretMaskingFilter())

    if not any(isinstance(f, ContextFilter) for f in logger.filters):
        logger.addFilter(ContextFilter())

    return logger  # type: ignore
