"""
Модуль ранеров для перезапуска дочерних процессов и внутрипроцессной перезагрузки функций.
"""

from __future__ import annotations

import abc
import importlib
import os
import signal
import subprocess
import sys
from typing import Any, Callable

from ..lifecycle import run_cleanup
from ..logger import setup_logger

logger = setup_logger()


class BaseRunner(abc.ABC):
    """Абстрактный базовый класс ранера для управления перезапуском приложений."""

    def __init__(self) -> None:
        self._is_running = False

    @property
    def is_running(self) -> bool:
        """Возвращает флаг состояния ранера."""
        return self._is_running

    @abc.abstractmethod
    def start(self) -> None:
        """Запускает процесс или целевую функцию."""

    @abc.abstractmethod
    def stop(self) -> None:
        """Останавливает процесс или целевую функцию."""

    def restart(self) -> None:
        """Выполняет перезапуск (остановка -> запуск)."""
        self.stop()
        self.start()


class SubprocessRunner(BaseRunner):
    """
    Ранер для запуска и управления внешним дочерним процессом.

    Args:
        command: Команда для выполнения (строка или список аргументов).
        graceful_timeout: Время ожидания в секундах перед принудительным завершением (kill).
        cwd: Рабочая директория для дочернего процесса.
    """

    def __init__(
        self,
        command: str | list[str],
        graceful_timeout: float = 3.0,
        cwd: str | None = None,
    ) -> None:
        super().__init__()
        self.command = command
        self.graceful_timeout = graceful_timeout
        self.cwd = cwd
        self._process: subprocess.Popen[bytes] | None = None

    @property
    def process(self) -> subprocess.Popen[bytes] | None:
        """Возвращает текущий экземпляр Popen."""
        return self._process

    def start(self) -> None:
        """Запускает внешнюю команду через subprocess.Popen."""
        if self._is_running and self._process is not None and self._process.poll() is None:
            return

        cmd_str = self.command if isinstance(self.command, str) else " ".join(self.command)
        logger.info(f"[watch] Запуск процесса: {cmd_str}")

        creationflags = 0
        if sys.platform == "win32":
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP

        try:
            self._process = subprocess.Popen(
                self.command,
                shell=isinstance(self.command, str),
                cwd=self.cwd,
                creationflags=creationflags,
            )
            self._is_running = True
        except Exception as err:
            logger.error(f"[watch] Не удалось запустить процесс: {err}")
            self._is_running = False

    def stop(self) -> None:
        """Мягко останавливает процесс (SIGTERM/SIGINT), затем вызывает kill() при необходимости."""
        if not self._is_running or self._process is None:
            return

        if self._process.poll() is not None:
            self._is_running = False
            self._process = None
            return

        pid = self._process.pid
        logger.info(f"[watch] Завершение процесса PID {pid}...")

        try:
            if sys.platform == "win32":
                try:
                    self._process.send_signal(signal.CTRL_BREAK_EVENT)
                except (OSError, ValueError):
                    self._process.terminate()
            else:
                self._process.terminate()

            self._process.wait(timeout=self.graceful_timeout)
        except (subprocess.TimeoutExpired, OSError):
            logger.warning(f"[watch] Процесс PID {pid} не ответил за {self.graceful_timeout}s. Принудительное уничтожение (KILL)...")
            try:
                self._process.kill()
                self._process.wait(timeout=1.0)
            except OSError:
                pass

        self._is_running = False
        self._process = None


class InProcessReloader(BaseRunner):
    """
    Ранер для внутрипроцессного перезапуска указанной функции с вызовом очистки lifecycle.

    Args:
        target: Строка формата "path.to.module:func_name".
        args: Опциональные позиционные аргументы функции.
        kwargs: Опциональные именованные аргументы функции.
    """

    def __init__(
        self,
        target: str,
        args: tuple[object, ...] | None = None,
        kwargs: dict[str, object] | None = None,
    ) -> None:
        super().__init__()
        if ":" not in target:
            raise ValueError(f"Некорректный формат target '{target}'. Ожидается 'module.path:func_name'")

        self.target = target
        self.module_name, self.func_name = target.split(":", 1)
        self.args = args or ()
        self.kwargs = kwargs or {}

    def _resolve_func(self) -> Callable[..., object]:
        """Динамически импортирует модуль и возвращает целевую функцию."""
        module = importlib.import_module(self.module_name)
        if not hasattr(module, self.func_name):
            raise AttributeError(f"Модуль '{self.module_name}' не содержит функцию '{self.func_name}'")
        func = getattr(module, self.func_name)
        if not callable(func):
            raise TypeError(f"Атрибут '{self.func_name}' в модуле '{self.module_name}' не является вызываемым объектом")
        return func

    def start(self) -> None:
        """Вызывает целевую функцию в текущем процессе."""
        logger.info(f"[watch] Вызов функции: {self.target}")
        try:
            func = self._resolve_func()
            self._is_running = True
            func(*self.args, **self.kwargs)
        except Exception as err:
            logger.error(f"[watch] Ошибка выполнения {self.target}: {err}")

    def stop(self) -> None:
        """Вызывает глобальную очистку коллбеков через trigger_cleanup()."""
        if not self._is_running:
            return

        logger.info("[watch] Выполнение глобальной очистки ресурсов (run_cleanup)...")
        try:
            run_cleanup()
        except Exception as err:
            logger.error(f"[watch] Ошибка при очистке ресурсов: {err}")

        self._is_running = False

    def restart(self) -> None:
        """Выполняет остановку, перезагружает модуль и снова вызывает функцию."""
        self.stop()

        # Перезагружаем целевой модуль
        if self.module_name in sys.modules:
            try:
                importlib.reload(sys.modules[self.module_name])
            except Exception as err:
                logger.error(f"[watch] Ошибка при перезагрузке модуля '{self.module_name}': {err}")

        self.start()
