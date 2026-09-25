"""
Ядро системы логирования.
Содержит основной класс логгера и функцию инициализации.
"""

from __future__ import annotations

import atexit
import logging  # chutils: ignore[ChutilsIntegrationRule]
import threading
import weakref
from typing import Any

from .internal.levels import (
    DEVDEBUG_LEVEL_NUM,
    MEDIUMDEBUG_LEVEL_NUM,
    LogLevel,
    LogLevelsMixin,
    init_custom_levels,
)
from .internal.utils import stop_all_async_loggers
from .masking import _GLOBAL_MASKS, _update_mask_re

# --- Глобальное состояние ---

atexit.register(stop_all_async_loggers)

init_custom_levels()

_active_loggers: weakref.WeakSet[ChutilsLogger] = weakref.WeakSet()
_global_handlers: list[logging.Handler] = []
_global_handlers_lock = threading.RLock()


def add_global_handler(handler: logging.Handler) -> None:
    """Добавляет глобальный обработчик для всех текущих и будущих логгеров chutils.

    Args:
        handler: Экземпляр logging.Handler.
    """
    with _global_handlers_lock:
        if handler not in _global_handlers:
            _global_handlers.append(handler)
        for log_obj in list(_active_loggers):
            if handler not in log_obj.handlers:
                log_obj.addHandler(handler)


def remove_global_handler(handler: logging.Handler) -> None:
    """Удаляет глобальный обработчик из реестра и из всех активных логгеров chutils.

    Args:
        handler: Экземпляр logging.Handler.
    """
    with _global_handlers_lock:
        if handler in _global_handlers:
            _global_handlers.remove(handler)
        for log_obj in list(_active_loggers):
            if handler in log_obj.handlers:
                log_obj.removeHandler(handler)


def get_global_handlers() -> list[logging.Handler]:
    """Возвращает копию списка зарегистрированных глобальных обработчиков.

    Returns:
        Список активных глобальных обработчиков logging.Handler.
    """
    with _global_handlers_lock:
        return list(_global_handlers)


def clear_global_handlers(remove_from_active: bool = True) -> None:
    """Очищает реестр глобальных обработчиков.

    Args:
        remove_from_active: Если True, также удаляет обработчики из активных логгеров.
    """
    with _global_handlers_lock:
        if remove_from_active:
            for handler in _global_handlers:
                for log_obj in list(_active_loggers):
                    if handler in log_obj.handlers:
                        log_obj.removeHandler(handler)
        _global_handlers.clear()


__all__ = [
    "DEVDEBUG_LEVEL_NUM",
    "MEDIUMDEBUG_LEVEL_NUM",
    "ChutilsLogger",
    "LogLevel",
    "add_global_handler",
    "clear_global_handlers",
    "get_global_handlers",
    "remove_global_handler",
    "setup_logger",
    "setup_logger_from_config",
]


class ChutilsLogger(logging.Logger, LogLevelsMixin):
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

    def __init__(self, name: str, level: int = logging.NOTSET) -> None:
        """Инициализирует экземпляр ChutilsLogger."""
        super().__init__(name, level)
        self._chutils_configured: bool = False
        with _global_handlers_lock:
            _active_loggers.add(self)

    def add_mask(self, value: str) -> None:
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

_file_handler_cache: dict[str, logging.FileHandler] = {}
_initialization_message_shown = False


def setup_logger(
    name: str = "app_logger",
    config_section_name: str | None = None,
    log_level: LogLevel | None = None,
    log_file_name: str | None = None,
    file_logging: bool | None = None,
    no_file: bool | None = None,
    force_reconfigure: bool = False,
    rotation_type: str | None = None,
    max_bytes: int | None = None,
    compress: bool | None = None,
    backup_count: int | None = None,
    encoding: str | None = None,
    when: str | None = None,
    interval: int | None = None,
    utc: bool | None = None,
    at_time: Any = None,
    json_format: bool | None = None,
    use_async: bool | None = None,
    custom_patterns: list[str] | None = None,
    use_predefined_patterns: list[str | list[str]] | None = None,
    propagate: bool | None = None,
    **kwargs: Any,
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

    ### Асинхронность:
    - Если `use_async=True`, логи записываются в очередь и обрабатываются в отдельном потоке.
    - Очередь блокирующая, что предотвращает потерю сообщений при переполнении.

    ### Маскирование:
    - Автоматическая замена секретов и паттернов на `[MASKED]`.
    - Поддержка предустановленных паттернов PII (`email`, `phone`, `credit_card`, `ssn`).

    Warning:
        Если ваше приложение использует Pydantic-модели или библиотеки вроде `pydantic-settings`
        для чтения конфигурации из внешних источников (например, `.env` или переменных окружения),
        рекомендуется явно передавать уровень логирования через параметр `log_level` для исключения
        рассинхронизации настроек с файлом `config.yml`.

    Args:
        name: Имя логгера. `app_logger` по умолчанию.
        config_section_name: Имя секции в конфиге (например, 'MyAuditLogger').
            Если указана, настройки из этой секции переопределяют настройки из общей секции `[Logging]`.
            Если не указана, используется только общая секция `[Logging]`.
        log_level: Уровень логирования (строка или LogLevel). Поддерживается псевдоним `level`.
        log_file_name: Имя файла лога. Если не указано, берется из конфига или 'app.log'.
        file_logging: Включить или отключить запись в файл (True/False). По умолчанию True.
        no_file: Псевдоним для отключения файлового логирования (no_file=True эквивалентно file_logging=False).
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
        json_format: Использовать ли JSON формат для логов.
        use_async: Использовать ли асинхронное логирование.
        custom_patterns: Список регулярных выражений для маскирования.
        use_predefined_patterns: Список имен предустановленных паттернов для маскирования.
        propagate: Передавать ли логи вверх по иерархии родительским логгерам (по умолчанию False).

        **kwargs: Дополнительные параметры для FileHandler (например, `delay=True`, `errors='ignore'`, `mode='a'`). Также поддерживает `level` как псевдоним `log_level`.

    Returns:
        Настроенный экземпляр ChutilsLogger.
    """
    if "level" in kwargs and log_level is None:
        log_level = kwargs.pop("level")

    valid_file_handler_kwargs = {"mode", "delay", "errors"}
    invalid_kwargs = set(kwargs.keys()) - valid_file_handler_kwargs
    if invalid_kwargs:
        bad_arg = min(invalid_kwargs)
        raise TypeError(
            f"setup_logger() got an unexpected keyword argument {bad_arg!r}"
        )

    from .internal.builder import LoggerBuilder

    builder = LoggerBuilder(name, config_section_name, **kwargs)

    return builder.build(
        log_level=log_level,
        force_reconfigure=force_reconfigure,
        use_async=use_async,
        json_format=json_format,
        log_file_name=log_file_name,
        file_logging=file_logging,
        no_file=no_file,
        rotation_type=rotation_type,
        max_bytes=max_bytes,
        compress=compress,
        backup_count=backup_count,
        encoding=encoding,
        when=when,
        interval=interval,
        utc=utc,
        at_time=at_time,
        custom_patterns=custom_patterns,
        use_predefined_patterns=use_predefined_patterns,
        propagate=propagate,
    )


def setup_logger_from_config(
    name: str = "app_logger",
    config_section_name: str | None = None,
    force_reconfigure: bool = False,
) -> ChutilsLogger:
    """Инициализирует логгер, используя настройки исключительно из файла конфигурации.

    Эта функция предоставляет простую сигнатуру и явно указывает на автонастройку
    из конфигурации (по умолчанию секция [Logging] в config.yml).

    Warning:
        Если ваше приложение использует Pydantic-модели или библиотеки вроде `pydantic-settings`
        для чтения конфигурации из внешних источников (например, `.env` или переменных окружения),
        вызов этой функции без аргументов может привести к рассинхронизации настроек. В таких
        случаях используйте `setup_logger(log_level=settings.log_level)` вместо этой функции.

    Args:
        name: Имя логгера. 'app_logger' по умолчанию.
        config_section_name: Имя секции в конфиге (например, 'AuditLogger').
            Если указана, настройки из этой секции переопределяют настройки из общей секции [Logging].
        force_reconfigure: Если True, принудительно перенастраивает существующий логгер.

    Returns:
        Настроенный экземпляр ChutilsLogger.
    """
    return setup_logger(
        name=name,
        config_section_name=config_section_name,
        force_reconfigure=force_reconfigure,
    )
