"""
Модуль для отслеживания изменений файловой системы в режиме Live Dev (hot-reload).

Предоставляет единый интерфейс BaseWatcher, реализацию на базе watchdog (WatchdogWatcher)
и нетребовательный к внешним зависимостям встроенный PollingWatcher.
"""

from __future__ import annotations

import abc
import fnmatch
import os
import threading
import time
from typing import Callable

from ..logger import setup_logger

logger = setup_logger()

# Проверяем доступность библиотеки watchdog
try:
    import watchdog.events
    import watchdog.observers
    HAS_WATCHDOG = True
except ImportError:
    HAS_WATCHDOG = False

DEFAULT_EXTENSIONS = ["py", "yaml", "yml", "json", "toml", "ini"]
DEFAULT_IGNORE_PATTERNS = [
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".idea",
    ".vscode",
    "*.pyc",
    "*.pyo",
    "*.swp",
]


class BaseWatcher(abc.ABC):
    """
    Абстрактный базовый класс для отслеживания изменений файлов.

    Args:
        paths: Директория или список директорий/файлов для отслеживания.
        extensions: Список расширений файлов без точки (например, ["py", "json"]).
        ignore_patterns: Список шаблонов путей/имен для игнорирования (fnmatch).
        debounce_seconds: Задержка пакетирования событий перезапуска в секундах.
        callback: Функция-коллбек, вызываемая при изменении файлов. Принимает список путей.
    """

    def __init__(
        self,
        paths: str | list[str],
        extensions: list[str] | None = None,
        ignore_patterns: list[str] | None = None,
        debounce_seconds: float = 0.5,
        callback: Callable[[list[str]], None] | None = None,
    ) -> None:
        if isinstance(paths, str):
            self.paths = [os.path.abspath(paths)]
        else:
            self.paths = [os.path.abspath(p) for p in paths]

        exts = extensions if extensions is not None else DEFAULT_EXTENSIONS
        # Нормализуем расширения (удаляем начальную точку, если приведена)
        self.extensions = {ext.lstrip(".").lower() for ext in exts}

        self.ignore_patterns = (
            ignore_patterns if ignore_patterns is not None else list(DEFAULT_IGNORE_PATTERNS)
        )
        self.debounce_seconds = debounce_seconds
        self.callback = callback

        self._is_running = False
        self._pending_files: set[str] = set()
        self._debounce_timer: threading.Timer | None = None
        self._lock = threading.Lock()

    @property
    def is_running(self) -> bool:
        """Возвращает статус запуска вотчера."""
        return self._is_running

    def _should_process_file(self, file_path: str) -> bool:
        """
        Проверяет, должен ли файл быть обработан в соответствии с расширениями и фильтрами.

        Args:
            file_path: Абсолютный или относительный путь к файлу.

        Returns:
            True, если файл подлежит отслеживанию, иначе False.
        """
        norm_path = os.path.normpath(file_path)
        parts = norm_path.split(os.sep)

        # Проверка игнорируемых директорий и шаблонов
        for pattern in self.ignore_patterns:
            pattern_clean = pattern.strip("/\\")
            if any(fnmatch.fnmatch(part, pattern_clean) for part in parts):
                return False
            if fnmatch.fnmatch(norm_path, pattern) or fnmatch.fnmatch(os.path.basename(norm_path), pattern):
                return False

        # Проверка расширения файла
        ext = os.path.splitext(file_path)[1].lstrip(".").lower()
        if self.extensions and ext not in self.extensions:
            return False

        return True

    def _notify_change(self, file_path: str) -> None:
        """
        Добавляет измененный файл в очередь и запускает таймер пакетирования (debounce).

        Args:
            file_path: Путь к измененному файлу.
        """
        if not self._should_process_file(file_path):
            return

        with self._lock:
            self._pending_files.add(file_path)
            if self._debounce_timer is not None:
                self._debounce_timer.cancel()

            self._debounce_timer = threading.Timer(self.debounce_seconds, self._flush_changes)
            self._debounce_timer.daemon = True
            self._debounce_timer.start()

    def _flush_changes(self) -> None:
        """Вызывает зарегистрированный коллбек с накопленным списком файлов."""
        with self._lock:
            files = list(self._pending_files)
            self._pending_files.clear()
            self._debounce_timer = None

        if files and self.callback is not None:
            try:
                self.callback(files)
            except Exception as err:
                logger.error(f"Ошибка при вызове коллбека вотчера: {err}")

    @abc.abstractmethod
    def start(self) -> None:
        """Запускает отслеживание файлов."""

    @abc.abstractmethod
    def stop(self) -> None:
        """Останавливает отслеживание файлов."""


class PollingWatcher(BaseWatcher):
    """
    Вотчер на базе периодического сканирования файловой системы (Fallback mode).

    Args:
        paths: Директория или список директорий/файлов для отслеживания.
        extensions: Список расширений файлов без точки.
        ignore_patterns: Шаблоны путей для игнорирования.
        debounce_seconds: Задержка дебаунса.
        poll_interval: Интервал между опросами файлов в секундах.
        callback: Коллбек для отправки списка изменившихся файлов.
    """

    def __init__(
        self,
        paths: str | list[str],
        extensions: list[str] | None = None,
        ignore_patterns: list[str] | None = None,
        debounce_seconds: float = 0.5,
        poll_interval: float = 1.0,
        callback: Callable[[list[str]], None] | None = None,
    ) -> None:
        super().__init__(
            paths=paths,
            extensions=extensions,
            ignore_patterns=ignore_patterns,
            debounce_seconds=debounce_seconds,
            callback=callback,
        )
        self.poll_interval = poll_interval
        self._mtimes: dict[str, float] = {}
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def _scan_files(self) -> dict[str, float]:
        """
        Сканирует отслеживаемые пути и возвращает словарь mtime файлов.

        Returns:
            Словарь {путь_к_файлу: время_модификации}.
        """
        current_mtimes: dict[str, float] = {}
        for target_path in self.paths:
            if not os.path.exists(target_path):
                continue

            if os.path.isfile(target_path):
                if self._should_process_file(target_path):
                    try:
                        current_mtimes[target_path] = os.path.getmtime(target_path)
                    except OSError:
                        pass
                continue

            for root, dirs, files in os.walk(target_path):
                # Исключаем диры, попадающие под ignore_patterns
                dirs[:] = [
                    d for d in dirs
                    if not any(
                        fnmatch.fnmatch(d, pat.strip("/\\"))
                        for pat in self.ignore_patterns
                    )
                ]

                for file_name in files:
                    full_path = os.path.join(root, file_name)
                    if self._should_process_file(full_path):
                        try:
                            current_mtimes[full_path] = os.path.getmtime(full_path)
                        except OSError:
                            pass

        return current_mtimes

    def _poll_loop(self) -> None:
        """Фоновый цикл сканирования изменений mtime файлов."""
        self._mtimes = self._scan_files()

        while not self._stop_event.is_set():
            time.sleep(self.poll_interval)
            if self._stop_event.is_set():
                break

            new_mtimes = self._scan_files()

            # Сравниваем старые и новые mtimes
            for path, new_mtime in new_mtimes.items():
                old_mtime = self._mtimes.get(path)
                if old_mtime is None or new_mtime > old_mtime:
                    self._notify_change(path)

            self._mtimes = new_mtimes

    def start(self) -> None:
        """Запускает фоновый поток опроса файловой системы."""
        if self._is_running:
            return

        self._stop_event.clear()
        self._is_running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()
        logger.debug(f"PollingWatcher запущен для путей: {self.paths}")

    def stop(self) -> None:
        """Останавливает фоновый опрос файлов."""
        if not self._is_running:
            return

        self._stop_event.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=2.0)

        with self._lock:
            if self._debounce_timer is not None:
                self._debounce_timer.cancel()
                self._debounce_timer = None

        self._is_running = False
        logger.debug("PollingWatcher остановлен.")


class _WatchdogEventHandler:
    """Внутренний обработчик событий watchdog."""

    def __init__(self, watcher: BaseWatcher) -> None:
        self.watcher = watcher

    def dispatch(self, event: object) -> None:
        """
        Диспетчеризует события файловой системы.

        Args:
            event: Объект события библиотеки watchdog.
        """
        is_directory = getattr(event, "is_directory", False)
        if is_directory:
            return

        src_path = getattr(event, "src_path", None)
        if isinstance(src_path, str):
            self.watcher._notify_change(src_path)


class WatchdogWatcher(BaseWatcher):
    """
    Вотчер на базе библиотеки watchdog.

    Args:
        paths: Директория или список директорий/файлов для отслеживания.
        extensions: Список расширений файлов без точки.
        ignore_patterns: Шаблоны путей для игнорирования.
        debounce_seconds: Задержка дебаунса.
        callback: Коллбек для отправки списка изменившихся файлов.
    """

    def __init__(
        self,
        paths: str | list[str],
        extensions: list[str] | None = None,
        ignore_patterns: list[str] | None = None,
        debounce_seconds: float = 0.5,
        callback: Callable[[list[str]], None] | None = None,
    ) -> None:
        super().__init__(
            paths=paths,
            extensions=extensions,
            ignore_patterns=ignore_patterns,
            debounce_seconds=debounce_seconds,
            callback=callback,
        )
        if not HAS_WATCHDOG:
            raise ImportError(
                "Библиотека watchdog не установлена. Используйте pip install watchdog"
            )

        self._observer: watchdog.observers.Observer | None = None

    def start(self) -> None:
        """Запускает Observer библиотеки watchdog."""
        if self._is_running:
            return

        import watchdog.events
        import watchdog.observers

        handler = watchdog.events.FileSystemEventHandler()
        inner_handler = _WatchdogEventHandler(self)
        handler.on_any_event = inner_handler.dispatch  # type: ignore[assignment]

        self._observer = watchdog.observers.Observer()
        for path in self.paths:
            if os.path.exists(path):
                watch_dir = path if os.path.isdir(path) else os.path.dirname(path)
                self._observer.schedule(handler, watch_dir, recursive=True)

        self._observer.start()
        self._is_running = True
        logger.debug(f"WatchdogWatcher запущен для путей: {self.paths}")

    def stop(self) -> None:
        """Останавливает Observer библиотеки watchdog."""
        if not self._is_running or self._observer is None:
            return

        self._observer.stop()
        self._observer.join(timeout=2.0)
        self._observer = None

        with self._lock:
            if self._debounce_timer is not None:
                self._debounce_timer.cancel()
                self._debounce_timer = None

        self._is_running = False
        logger.debug("WatchdogWatcher остановлен.")


def get_watcher(
    paths: str | list[str],
    extensions: list[str] | None = None,
    ignore_patterns: list[str] | None = None,
    debounce_seconds: float = 0.5,
    poll_interval: float = 1.0,
    callback: Callable[[list[str]], None] | None = None,
) -> BaseWatcher:
    """
    Фабричная функция для создания наилучшего доступного файлового вотчера.

    Использует WatchdogWatcher, если установлена библиотека watchdog,
    иначе выводит предупреждение в лог и использует PollingWatcher.

    Args:
        paths: Путь или список путей для отслеживания.
        extensions: Расширения файлов для отслеживания.
        ignore_patterns: Шаблоны для игнорирования.
        debounce_seconds: Таймаут пакетирования событий.
        poll_interval: Интервал опроса для PollingWatcher.
        callback: Коллбек при изменении файлов.

    Returns:
        Экземпляр BaseWatcher (WatchdogWatcher или PollingWatcher).
    """
    if HAS_WATCHDOG:
        try:
            return WatchdogWatcher(
                paths=paths,
                extensions=extensions,
                ignore_patterns=ignore_patterns,
                debounce_seconds=debounce_seconds,
                callback=callback,
            )
        except Exception as err:
            logger.warning(f"Не удалось инициализировать WatchdogWatcher: {err}. Используется PollingWatcher.")

    logger.warning(
        "[WARNING] watchdog не установлен. Используется медленный fallback-опрос диска. "
        "Установите watchdog для лучшей производительности: pip install watchdog"
    )
    return PollingWatcher(
        paths=paths,
        extensions=extensions,
        ignore_patterns=ignore_patterns,
        debounce_seconds=debounce_seconds,
        poll_interval=poll_interval,
        callback=callback,
    )
