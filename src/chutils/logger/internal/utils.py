import logging  # chutils: ignore[ChutilsIntegrationRule]
import logging.handlers
from pathlib import Path

from ... import config
from ...fs import ensure_dir

_LOG_DIR: str | None = None
"""Глобальное состояние директории логов."""

_async_listeners: list[logging.handlers.QueueListener] = []
"""Глобальный список слушателей очереди асинхронного логирования."""


def get_log_dir() -> str | None:
    """"Лениво" получает и кэширует путь к директории логов.
    Создает директорию 'logs' в корне проекта при первом обращении.

    Returns:
        Путь к директории логов или None при ошибке.
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
            ensure_dir(log_path)
            logging.info("Создана директория для логов: %s", log_path)
        except OSError as e:
            logging.error("Не удалось создать директорию для логов %s: %s", log_path, e)
            return None

    _LOG_DIR = str(log_path)
    return _LOG_DIR


def stop_all_async_loggers() -> None:
    """
    Останавливает все активные асинхронные слушатели логов.
    """
    global _async_listeners
    for listener in _async_listeners:
        try:
            listener.stop()
        except Exception:
            pass
    _async_listeners.clear()


def register_async_listener(listener: logging.handlers.QueueListener) -> None:
    """Регистрирует новый асинхронный слушатель.

    Args:
        listener: Объект QueueListener для регистрации.
    """
    global _async_listeners
    _async_listeners.append(listener)
