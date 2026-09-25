"""
Перехват стандартного логирования Python (InterceptHandler и capture_standard_logging).
"""

from __future__ import annotations

import logging  # chutils: ignore[ChutilsIntegrationRule]
import sys
import threading

_is_intercepting = threading.local()

DEFAULT_INTERCEPT_MODULES: tuple[str, ...] = (
    "uvicorn",
    "uvicorn.access",
    "uvicorn.error",
    "fastapi",
    "httpx",
    "httpcore",
    "urllib3",
    "asyncio",
    "playwright",
    "nodriver",
)


class InterceptHandler(logging.Handler):
    """Обработчик для перенаправления стандартных записей logging в chutils.

    Перехватывает записи `logging.LogRecord` от стандартных или сторонних библиотек
    и направляет их в целевой логгер `chutils`, сохраняя уровень, форматирование
    и метаданные вызова.
    """

    def __init__(
        self,
        target_logger_name: str = "app_logger",
        level: int = logging.NOTSET,
    ) -> None:
        """Инициализирует InterceptHandler.

        Args:
            target_logger_name: Имя логгера chutils, принимающего записи.
            level: Уровень фильтрации обработчика.
        """
        super().__init__(level=level)
        self.target_logger_name = target_logger_name

    def emit(self, record: logging.LogRecord) -> None:
        """Перенаправляет LogRecord в целевой логгер chutils.

        Args:
            record: Запись лога.
        """
        if getattr(_is_intercepting, "active", False):
            return

        # Не перехватываем записи самого целевого логгера во избежание рекурсии
        if record.name == self.target_logger_name:
            return

        dest_logger = logging.getLogger(self.target_logger_name)
        if not dest_logger.isEnabledFor(record.levelno):
            return

        _is_intercepting.active = True
        try:
            # Находим фрейм вызывающего кода вне модуля logging
            frame = sys._getframe(2)
            while frame and frame.f_code.co_filename == logging.__file__:
                frame = frame.f_back  # type: ignore[assignment]

            if frame:
                record.pathname = frame.f_code.co_filename
                record.lineno = frame.f_lineno
                record.funcName = frame.f_code.co_name

            dest_logger.handle(record)
        except Exception:
            self.handleError(record)
        finally:
            _is_intercepting.active = False


def capture_standard_logging(
    modules: list[str] | tuple[str, ...] | None = None,
    target_logger: str = "app_logger",
    level: int | str = logging.INFO,
    intercept_root: bool = True,
) -> InterceptHandler:
    """Перехватывает логи стандартных и сторонних библиотек в логгер chutils.

    Позволяет централизованно собирать логи от библиотек вроде uvicorn, requests,
    httpx, nodriver и форматировать их через chutils (Rich, файлы, Qt).

    Args:
        modules: Список имен логгеров библиотек для явного перехвата.
            Если None, используется DEFAULT_INTERCEPT_MODULES.
        target_logger: Имя логгера chutils, принимающего записи.
        level: Минимальный уровень логирования.
        intercept_root: Перехватывать ли корневой логгер logging.root.

    Returns:
        Экземпляр установленного InterceptHandler.
    """
    from .core import setup_logger

    dest_log = logging.getLogger(target_logger)
    if not getattr(dest_log, "_chutils_configured", False):
        setup_logger(target_logger)

    lvl_num = logging.getLevelName(level.upper()) if isinstance(level, str) else level
    if not isinstance(lvl_num, int):
        lvl_num = logging.INFO

    handler = InterceptHandler(target_logger_name=target_logger, level=lvl_num)

    target_modules = DEFAULT_INTERCEPT_MODULES if modules is None else tuple(modules)
    for mod_name in target_modules:
        mod_logger = logging.getLogger(mod_name)
        mod_logger.handlers.clear()
        mod_logger.propagate = False
        mod_logger.setLevel(lvl_num)
        mod_logger.addHandler(handler)

    if intercept_root:
        root_logger = logging.getLogger()
        root_logger.handlers.clear()
        root_logger.setLevel(lvl_num)
        root_logger.addHandler(handler)

    return handler


intercept_all = capture_standard_logging


def restore_standard_logging(
    modules: list[str] | tuple[str, ...] | None = None,
    restore_root: bool = True,
) -> None:
    """Восстанавливает стандартное поведение логгеров, удаляя InterceptHandler.

    Args:
        modules: Список имен логгеров модулей для восстановления.
        restore_root: Восстановить ли корневой логгер logging.root.
    """
    target_modules = DEFAULT_INTERCEPT_MODULES if modules is None else tuple(modules)
    for mod_name in target_modules:
        mod_logger = logging.getLogger(mod_name)
        for h in mod_logger.handlers[:]:
            if isinstance(h, InterceptHandler):
                mod_logger.removeHandler(h)
        mod_logger.propagate = True

    if restore_root:
        root_logger = logging.getLogger()
        for h in root_logger.handlers[:]:
            if isinstance(h, InterceptHandler):
                root_logger.removeHandler(h)


__all__ = [
    "DEFAULT_INTERCEPT_MODULES",
    "InterceptHandler",
    "capture_standard_logging",
    "intercept_all",
    "restore_standard_logging",
]
