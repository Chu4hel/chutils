import logging
import time
from pathlib import Path
from typing import List, Callable

from chutils.exceptions import OptionalDependencyError

from .manager import _cm
from .utils import find_project_root
from .. import env

# Настраиваем логгер
logger = logging.getLogger(__name__)

_DEBOUNCE_SECONDS = 1.0
"Константа для debounce (секунды)"


def on_config_change(callback: Callable[[], None]) -> None:
    """
    Регистрирует функцию обратного вызова, которая будет вызвана при изменении конфигурации.

    Args:
        callback: Функция без аргументов.
    """
    if _cm.add_callback(callback):
        logger.debug("Зарегистрирован коллбэк на изменение конфигурации: %s",
                     getattr(callback, '__name__', str(callback)))


class ConfigChangeHandler:
    """
    Обработчик событий изменения файлов конфигурации для watchdog.
    """

    def __init__(self, watched_files: List[str]):
        self.watched_files = [str(Path(f).absolute()) for f in watched_files]

    def dispatch(self, event):
        """Метод вызывается при любом событии в директории."""
        if event.is_directory:
            return

        # Проверяем, что изменен именно один из наших файлов конфигурации
        event_path = str(Path(event.src_path).absolute())
        if event_path in self.watched_files:
            self._on_modified()

    @staticmethod
    def _on_modified():
        current_time = time.monotonic()

        # Подавляем уведомление, если это было внутреннее сохранение с notify=False
        if _cm.check_internal_save(0.5):
            logger.debug("Hot-Reload подавлен (внутреннее сохранение).")
            return

        if current_time - _cm.last_reload_time < _DEBOUNCE_SECONDS:
            return

        _cm.last_reload_time = current_time
        logger.info("Обнаружено изменение конфигурации. Сброс кэша...")

        # Сбрасываем кэш
        _cm.clear_cache()

        # Вызываем коллбэки
        for callback in _cm.get_callbacks():
            try:
                callback()
            except Exception as e:
                logger.error("Ошибка при выполнении коллбэка %s: %s", getattr(callback, '__name__', str(callback)), e)


def start_config_watcher() -> bool:
    """
    Запускает фоновый процесс отслеживания изменений в файлах конфигурации.

    Требует установленного пакета watchdog.

    Returns:
        True, если watcher успешно запущен.

    Raises:
        OptionalDependencyError: Если пакет `watchdog` не установлен.
    """
    if not env.WATCHDOG_AVAILABLE:
        raise OptionalDependencyError(
            "Пакет 'watchdog' необходим для работы hot-reload. "
            "Установите его с помощью 'pip install chutils[watch]' или 'poetry add watchdog'.",
            dependency="watchdog"
        )

    from watchdog.observers import Observer

    if _cm.observer and _cm.observer.is_alive():
        logger.debug("Watcher конфигурации уже запущен.")
        return True

    if not _cm.paths_initialized:
        _cm.initialize_paths(find_project_root)

    main_path, env_path, local_path = _cm.get_all_config_paths()
    files_to_watch = []
    if main_path and Path(main_path).exists():
        files_to_watch.append(main_path)
    if env_path and Path(env_path).exists():
        files_to_watch.append(env_path)
    if local_path and Path(local_path).exists():
        files_to_watch.append(local_path)

    # Добавляем файл фича-флагов, если он есть
    if _cm.features_file_path and Path(_cm.features_file_path).exists():
        files_to_watch.append(_cm.features_file_path)

    if not files_to_watch:
        logger.warning("Нет файлов конфигурации для отслеживания.")
        return False

    # Директории, которые нужно отслеживать (уникальные)
    dirs_to_watch = {str(Path(f).parent.absolute()) for f in files_to_watch}

    _cm.observer = Observer()
    handler = ConfigChangeHandler(files_to_watch)

    for d in dirs_to_watch:
        _cm.observer.schedule(handler, d, recursive=False)

    _cm.observer.daemon = True
    _cm.observer.start()
    logger.info("Запущен мониторинг изменений файлов конфигурации: %s", files_to_watch)
    return True


def stop_config_watcher():
    """
    Останавливает процесс отслеживания изменений конфигурации.
    """
    if _cm.observer:
        _cm.observer.stop()
        _cm.observer.join()
        _cm.observer = None
        logger.info("Мониторинг изменений конфигурации остановлен.")
