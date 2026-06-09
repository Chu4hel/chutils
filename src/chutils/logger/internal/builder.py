from __future__ import annotations

import datetime
import logging
import logging.handlers
import os
import queue
from pathlib import Path
from typing import Optional, Any, List, Union, TYPE_CHECKING, cast

if TYPE_CHECKING:
    from ..core import ChutilsLogger

from .levels import LogLevel, MEDIUMDEBUG_LEVEL_NUM, DEVDEBUG_LEVEL_NUM
from .utils import get_log_dir, register_async_listener
from ..formatters import JSON_LOGGER_AVAILABLE, ChutilsJsonFormatter
from ..handlers import (
    SafeTimedRotatingFileHandler,
    CompressingRotatingFileHandler,
    CompressingTimedRotatingFileHandler
)
from ..masking import (
    SecretMaskingFilter,
    _GLOBAL_MASKS,
    _CUSTOM_PATTERNS,
    _update_mask_re,
    PREDEFINED_PATTERNS
)
from ... import config as config_api
from ... import env as env_api
from ...context import ContextFilter


class LoggerBuilder:
    """
    Класс-строитель для инкапсуляции сложной логики настройки логгера.

    Этот класс отделяет процесс конфигурации (сборку обработчиков, настройку форматеров,
    маскирование и ротацию) от основного класса логгера, делая код более модульным.
    """

    def __init__(
            self,
            name: str,
            config_section_name: Optional[str] = None,
            **kwargs: Any
    ):
        """
        Инициализирует строитель для конкретного логгера.

        Args:
            name: Имя логгера.
            config_section_name: Имя секции в конфиге для переопределения стандартных настроек.
            **kwargs: Дополнительные параметры для FileHandler.
        """
        self.name = name
        self.config_section_name = config_section_name
        self.kwargs = kwargs

        self.logger = logging.getLogger(name)
        self.cfg = config_api.get_config()

        # Получаем настройки из конфига (Logging + опционально специфичная секция)
        default_settings: dict[str, Any] = self.cfg.get('Logging', {})
        specific_settings: dict[str, Any] = {}
        if config_section_name:
            specific_settings = self.cfg.get(config_section_name, {})

        self.settings: dict[str, Any] = {**default_settings, **specific_settings}

    def build(
            self,
            log_level: Optional[LogLevel] = None,
            force_reconfigure: bool = False,
            use_async: Optional[bool] = None,
            json_format: Optional[bool] = None,
            log_file_name: Optional[str] = None,
            rotation_type: Optional[str] = None,
            max_bytes: Optional[int] = None,
            compress: Optional[bool] = None,
            backup_count: Optional[int] = None,
            encoding: Optional[str] = None,
            when: Optional[str] = None,
            interval: Optional[int] = None,
            utc: Optional[bool] = None,
            at_time: Any = None,
            custom_patterns: Optional[List[str]] = None,
            use_predefined_patterns: Optional[List[Union[str, List[str]]]] = None,
    ) -> 'ChutilsLogger':
        """
        Основной метод сборки и настройки логгера.

        Выполняет все этапы конфигурации: определение уровня, настройку консоли,
        создание файловых обработчиков, применение асинхронности и маскирование.

        Returns:
            Настроенный экземпляр ChutilsLogger.
        """
        # Слияние настроек из конфига и переданных аргументов (overrides)
        overrides: dict[str, Any] = {
            'log_file_name': log_file_name,
            'rotation_type': rotation_type,
            'max_bytes': max_bytes,
            'compress': compress,
            'backup_count': backup_count,
            'encoding': encoding,
            'when': when,
            'interval': interval,
            'utc': utc,
            'at_time': at_time,
            'custom_patterns': custom_patterns,
            'use_predefined_patterns': use_predefined_patterns
        }
        # Убираем None, чтобы не перезаписать значения из конфига пустышками
        overrides = {k: v for k, v in overrides.items() if v is not None}
        params: dict[str, Any] = {**self.settings, **overrides}

        # 1. Настройка ширины консоли
        self._apply_console_width()

        # 2. Определение и установка уровня
        level_int = self._get_level_int(log_level)
        self.logger.setLevel(level_int)
        self.logger.propagate = False

        if self.logger.hasHandlers() and not force_reconfigure:
            return cast('ChutilsLogger', self.logger)

        if force_reconfigure:
            self._clear_handlers()

        # 3. Подготовка обработчиков (консоль + файл)
        target_handlers = self._create_handlers(level_int, json_format, **params)

        # 4. Применение асинхронности или прямая привязка
        final_use_async = self._is_async(use_async)
        if final_use_async:
            self._apply_async_logging(target_handlers, **params)
        else:
            for handler in target_handlers:
                self.logger.addHandler(handler)

        # 5. Настройка маскирования секретов и PII
        self._apply_masking(custom_patterns, use_predefined_patterns)

        # 6. Добавление стандартных фильтров (маскирование + контекст)
        self._add_standard_filters()

        return cast('ChutilsLogger', self.logger)

    def _get_level_int(self, log_level: Optional[LogLevel]) -> int:
        """Определяет числовое значение уровня логирования."""
        if log_level is not None:
            level_str = log_level.value if isinstance(log_level, LogLevel) else str(log_level).upper()
        else:
            level_str = str(self.settings.get('log_level', 'INFO')).upper()

        # Явное использование констант для предотвращения удаления импортов и как fallback
        if level_str == "MEDIUMDEBUG":
            return MEDIUMDEBUG_LEVEL_NUM
        if level_str == "DEVDEBUG":
            return DEVDEBUG_LEVEL_NUM

        level_int = logging.getLevelName(level_str)
        if not isinstance(level_int, int):
            self.logger.warning("Неизвестный уровень логирования: '%s'. Используется INFO.", level_str)
            return logging.INFO
        return level_int

    def _apply_console_width(self) -> None:
        """Устанавливает ширину консоли из настроек CLI."""
        cli_settings: dict[str, Any] = self.cfg.get('CLI', {})
        config_width = cli_settings.get('console_width')
        if config_width is not None:
            try:
                from chutils.cli_utils import set_console_width
                set_console_width(int(config_width))
            except (ValueError, TypeError, ImportError):
                pass

    def _clear_handlers(self) -> None:
        """Закрывает и удаляет все существующие обработчики логгера."""
        from ..core import _file_handler_cache
        for handler in self.logger.handlers[:]:
            if isinstance(handler, logging.FileHandler):
                if handler.baseFilename in _file_handler_cache:
                    del _file_handler_cache[handler.baseFilename]
            handler.close()
            self.logger.removeHandler(handler)

    def _is_async(self, explicit_use_async: Optional[bool]) -> bool:
        """Определяет, должен ли логгер работать в асинхронном режиме."""
        if explicit_use_async is not None:
            return explicit_use_async
        val = self.settings.get('use_async', False)
        if isinstance(val, str):
            return val.lower() in ["true", "1", "yes", "y"]
        return bool(val)

    def _create_handlers(self, level_int: int, json_format_arg: Optional[bool], **params: Any) -> List[logging.Handler]:
        """Создает список обработчиков для логгера."""
        # Определение основного формата
        formatter = self._get_formatter(json_format_arg)

        # Консольный обработчик
        console_handler = self._create_console_handler(level_int, formatter, json_format_arg)
        target_handlers: List[logging.Handler] = [console_handler]

        # Файловый обработчик (если включен)
        file_handler = self._create_file_handler(formatter, **params)
        if file_handler:
            target_handlers.append(file_handler)

        return target_handlers

    def _get_formatter(self, json_format: Optional[bool]) -> logging.Formatter:
        """Создает и возвращает подходящий форматер (текстовый или JSON)."""
        env_no_time = os.getenv("CH_LOG_NO_TIME", "").lower() in ["true", "1", "yes", "y"]
        log_format = '%(name)s - %(levelname)s %(context)s- %(message)s' if env_no_time else \
            '%(asctime)s - %(name)s - %(levelname)s %(context)s- %(message)s'

        if self._should_use_json(json_format):
            if JSON_LOGGER_AVAILABLE:
                return ChutilsJsonFormatter('%(asctime)s %(name)s %(levelname)s %(message)s')
            self.logger.warning(
                "Запрошен формат JSON, но пакет 'python-json-logger' не установлен. Используется стандартный текстовый формат."
            )

        return logging.Formatter(log_format)

    def _should_use_json(self, explicit_json: Optional[bool]) -> bool:
        """Определяет, нужно ли использовать JSON формат."""
        env_json = os.getenv("CH_LOG_JSON", "").lower()
        if env_json:
            return env_json in ["true", "1", "yes", "y"]
        if explicit_json is not None:
            return explicit_json
        val = self.settings.get('json_format', False)
        return val.lower() in ["true", "1", "yes", "y"] if isinstance(val, str) else bool(val)

    def _create_console_handler(self, level_int: int, formatter: logging.Formatter,
                                json_format: Optional[bool]) -> logging.Handler:
        """Создает обработчик для вывода в консоль (Rich или стандартный)."""
        env_no_time = os.getenv("CH_LOG_NO_TIME", "").lower() in ["true", "1", "yes", "y"]

        handler: logging.Handler
        if env_api.is_rich_enabled() and not self._should_use_json(json_format):
            from rich.logging import RichHandler
            from chutils.cli_utils import get_console, FallbackConsole

            console_obj = get_console(stderr=True)
            handler = RichHandler(
                console=console_obj if not isinstance(console_obj, FallbackConsole) else None,
                rich_tracebacks=True,
                markup=True,
                tracebacks_show_locals=True,
                show_time=not env_no_time,
                show_path=False
            )
        else:
            handler = logging.StreamHandler()
            handler.setFormatter(formatter)

        handler.setLevel(level_int)
        return handler

    def _create_file_handler(self, formatter: logging.Formatter, **params: Any) -> Optional[logging.Handler]:
        """Создает и настраивает файловый обработчик."""
        from ..core import _file_handler_cache
        # Используем импорт внутри функции, чтобы избежать циклической зависимости и иметь доступ к переменным
        import chutils.logger.core as core

        env_no_file = os.getenv("CH_LOG_NO_FILE", "").lower() in ["true", "1", "yes", "y"]
        log_dir = get_log_dir()

        filename = params.get('log_file_name') or self.settings.get('log_file_name', 'app.log')

        if env_no_file or not log_dir or not filename:
            # Предотвращаем спам варнингом
            if not core._initialization_message_shown:
                self.logger.warning("Директория для логов не настроена. Файловое логирование отключено.")
                core._initialization_message_shown = True
            return None

        log_path = Path(filename) if Path(filename).is_absolute() else Path(log_dir) / filename
        path_str = str(log_path)

        if path_str in _file_handler_cache:
            return _file_handler_cache[path_str]

        try:
            handler = self._instantiate_file_handler(path_str, **params)
            handler.setFormatter(formatter)
            _file_handler_cache[path_str] = handler
            core._initialization_message_shown = True
            return handler
        except Exception as e:
            self.logger.error("Не удалось настроить файловый обработчик логов для %s: %s", path_str, e)
            return None

    def _instantiate_file_handler(self, path: str, **params: Any) -> logging.FileHandler:
        """Инстанцирует конкретный класс файлового обработчика с параметрами ротации."""
        rtype = params.get('rotation_type') or self.settings.get('rotation_type', 'time')

        # Собираем базовые параметры
        backup_count = int(params.get('backup_count') or self.settings.get('log_backup_count', 3))
        encoding = params.get('encoding') or self.settings.get('encoding', 'utf-8')

        # Сжатие
        compress = params.get('compress')
        if compress is None:
            cval = self.settings.get('compress', False)
            compress = cval.lower() in ['true', '1'] if isinstance(cval, str) else bool(cval)

        h_class: type[logging.FileHandler]
        if rtype == 'size':
            max_bytes = int(params.get('max_bytes') or self.settings.get('max_bytes', 5 * 1024 * 1024))
            h_class = CompressingRotatingFileHandler if compress else logging.handlers.RotatingFileHandler
            return h_class(path, maxBytes=max_bytes, backupCount=backup_count, encoding=encoding, **self.kwargs)

        # Ротация по времени
        when = params.get('when') or self.settings.get('when', 'D')
        interval = int(params.get('interval') or self.settings.get('interval', 1))
        utc = params.get('utc')
        if utc is None:
            uval = self.settings.get('utc', False)
            utc = uval.lower() in ['true', '1'] if isinstance(uval, str) else bool(uval)

        at_time = params.get('at_time')
        if isinstance(at_time, str):
            try:
                at_time = datetime.time.fromisoformat(at_time)
            except (TypeError, ValueError):
                self.logger.error(
                    "Неверный формат времени '%s' для 'at_time' в конфиге. Используется None.",
                    at_time
                )
                at_time = None

        h_class = CompressingTimedRotatingFileHandler if compress else SafeTimedRotatingFileHandler
        h_args: dict[str, Any] = {
            'when': when,
            'interval': interval,
            'backupCount': backup_count,
            'encoding': encoding,
            'utc': utc
        }
        if at_time:
            h_args['atTime'] = at_time

        return h_class(path, **h_args, **self.kwargs)

    def _apply_async_logging(self, handlers: List[logging.Handler], **params: Any) -> None:
        """Настраивает асинхронную обработку логов через очередь."""
        max_size = int(params.get('async_max_queue_size') or self.settings.get('async_max_queue_size', 10000))
        log_queue: queue.Queue[logging.LogRecord] = queue.Queue(max_size)

        self.logger.addHandler(logging.handlers.QueueHandler(log_queue))

        listener = logging.handlers.QueueListener(log_queue, *handlers, respect_handler_level=True)
        listener.start()
        register_async_listener(listener)

    def _apply_masking(self, custom_patterns_arg: Optional[List[str]],
                       use_predefined_arg: Optional[List[Union[str, List[str]]]]) -> None:
        """Настраивает правила маскирования данных (секреты, регулярки, PII)."""
        # 1. Литеральные строки из конфига (старое поведение)
        mask_patterns = self.settings.get('mask_patterns', [])
        if isinstance(mask_patterns, list):
            for pattern in mask_patterns:
                if not pattern: continue
                secret_value = self.settings.get(pattern)
                if secret_value and isinstance(secret_value, str):
                    _GLOBAL_MASKS.add(secret_value)
                elif isinstance(pattern, str):
                    _GLOBAL_MASKS.add(pattern)

        # 2. Кастомные регулярные выражения (из аргументов и конфига)
        all_custom: list[str] = (custom_patterns_arg or []) + list(self.settings.get('custom_mask_patterns', []))
        for p in all_custom:
            if isinstance(p, str) and p:
                _CUSTOM_PATTERNS.add(p)

        # 3. Предустановленные паттерны (PII)
        config_predefined = self.settings.get('use_predefined_masking', [])
        all_predefined: list[Any] = (use_predefined_arg or []) + list(config_predefined)

        for item in all_predefined:
            # Обработка случая, когда передан список имен паттернов
            names = item if isinstance(item, list) else [item]
            for name in names:
                if isinstance(name, str) and name in PREDEFINED_PATTERNS:
                    _CUSTOM_PATTERNS.add(PREDEFINED_PATTERNS[name])

        _update_mask_re()

    def _add_standard_filters(self) -> None:
        """Добавляет фильтры маскирования и контекста, если они еще не добавлены."""
        if not any(isinstance(f, SecretMaskingFilter) for f in self.logger.filters):
            self.logger.addFilter(SecretMaskingFilter())
        if not any(isinstance(f, ContextFilter) for f in self.logger.filters):
            self.logger.addFilter(ContextFilter())
