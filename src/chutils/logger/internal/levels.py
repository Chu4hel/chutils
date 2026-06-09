from __future__ import annotations

import logging
from enum import Enum
from typing import Any, cast

# --- Пользовательские уровни логирования ---

DEVDEBUG_LEVEL_NUM = 9
DEVDEBUG_LEVEL_NAME = "DEVDEBUG"
MEDIUMDEBUG_LEVEL_NUM = 15
MEDIUMDEBUG_LEVEL_NAME = "MEDIUMDEBUG"


def init_custom_levels() -> None:
    """
    Регистрирует пользовательские уровни в модуле logging.
    Безопасно для повторного вызова.
    """
    if logging.getLevelName(MEDIUMDEBUG_LEVEL_NUM) != MEDIUMDEBUG_LEVEL_NAME:
        logging.addLevelName(MEDIUMDEBUG_LEVEL_NUM, MEDIUMDEBUG_LEVEL_NAME)
    if logging.getLevelName(DEVDEBUG_LEVEL_NUM) != DEVDEBUG_LEVEL_NAME:
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


class LogLevelsMixin:
    """
    Миксин для добавления методов пользовательских уровней в Logger.
    """

    def mediumdebug(self, message: str, *args: Any, **kws: Any) -> None:
        """
        Логирует сообщение с уровнем MEDIUMDEBUG (15).
        """
        _self = cast(logging.Logger, self)
        if _self.isEnabledFor(MEDIUMDEBUG_LEVEL_NUM):
            _self._log(MEDIUMDEBUG_LEVEL_NUM, message, args, **kws)

    def devdebug(self, message: str, *args: Any, **kws: Any) -> None:
        """
        Логирует сообщение с уровнем DEVDEBUG (9).
        """
        _self = cast(logging.Logger, self)
        if _self.isEnabledFor(DEVDEBUG_LEVEL_NUM):
            _self._log(DEVDEBUG_LEVEL_NUM, message, args, **kws)
