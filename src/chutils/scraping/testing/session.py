"""
Менеджер живых браузерных сессий для сквозного (live) тестирования скраперов.

Обеспечивает создание изолированных временных профилей (user_data_dir),
отслеживание запущенных процессов браузеров (nodriver, Playwright, Selenium)
и их гарантированное завершение (teardown / kill zombies) даже при сбоях тестов.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import time
from pathlib import Path
from types import TracebackType
from typing import Any

from typing_extensions import Self

import logging  # chutils: ignore[ChutilsIntegrationRule]
from chutils.fs import ensure_dir
from chutils.lifecycle import register_cleanup, unregister_cleanup

logger = logging.getLogger(__name__)  # chutils: ignore[ChutilsIntegrationRule]


class LiveBrowserSession:
    """
    Контекстный менеджер изолированной сессии реального браузера.

    Создает временный каталог профиля (`user_data_dir`), регистрирует запущенные
    процессы браузера и гарантирует их принудительное уничтожение при выходе или
    аварийном завершении приложения через `chutils.lifecycle`.
    """

    def __init__(
        self,
        browser_name: str = "chromium",
        user_data_dir: Path | str | None = None,
        auto_cleanup_dir: bool = True,
        keep_profile_on_failure: bool = False,
    ) -> None:
        """Инициализирует сессию живого браузера.

        Args:
            browser_name: Название браузера (например, "chromium", "chrome", "firefox").
            user_data_dir: Пользовательский путь к каталогу профиля. Если None,
                создается временный каталог с префиксом `chutils_live_browser_`.
            auto_cleanup_dir: Автоматически удалять каталог профиля при очистке.
            keep_profile_on_failure: Не удалять профиль при возникновении исключения
                в контекстном менеджере (для отладки упавших тестов).
        """
        self.browser_name = browser_name
        self.auto_cleanup_dir = auto_cleanup_dir
        self.keep_profile_on_failure = keep_profile_on_failure
        self._custom_dir = user_data_dir is not None

        if user_data_dir is not None:
            self.user_data_dir = Path(user_data_dir).resolve()
        else:
            temp_dir = tempfile.mkdtemp(prefix=f"chutils_live_browser_{browser_name}_")
            self.user_data_dir = Path(temp_dir).resolve()

        self._tracked_processes: list[Any] = []
        self._is_active = False
        self._cleanup_registered = False

    @property
    def is_active(self) -> bool:
        """Возвращает флаг активности текущей сессии."""
        return self._is_active

    def track_process(self, process_or_pid: Any) -> None:
        """Регистрирует процесс браузера для отслеживания и гарантированного teardown.

        Args:
            process_or_pid: Объект процесса (subprocess.Popen, nodriver Browser,
                playwright process) или числовой PID.
        """
        if process_or_pid not in self._tracked_processes:
            self._tracked_processes.append(process_or_pid)
            logger.debug(
                "LiveBrowserSession: отслеживается процесс %s (всего: %d)",
                process_or_pid,
                len(self._tracked_processes),
            )

    def cleanup(self) -> None:
        """Принудительно останавливает все отслеживаемые процессы и удаляет профиль."""
        # 1. Завершаем все отслеживаемые процессы
        for proc in list(self._tracked_processes):
            self._terminate_process(proc)
        self._tracked_processes.clear()

        # 2. Удаляем каталог профиля при необходимости
        if self.auto_cleanup_dir and self.user_data_dir.exists():
            self._remove_directory(self.user_data_dir)

        # 3. Снимаем регистрацию в chutils.lifecycle
        if self._cleanup_registered:
            unregister_cleanup(self._on_lifecycle_shutdown)
            self._cleanup_registered = False

        self._is_active = False

    def _terminate_process(self, proc: Any) -> None:
        """Завершает переданный процесс или PID с гарантированным fallback на kill."""
        try:
            # Проверяем метод is_running
            is_running_fn = getattr(proc, "is_running", None)
            if callable(is_running_fn):
                try:
                    if not is_running_fn():
                        return
                except Exception:
                    pass

            # Если объект имеет terminate / kill
            terminate_fn = getattr(proc, "terminate", None)
            kill_fn = getattr(proc, "kill", None)

            if callable(terminate_fn):
                try:
                    terminate_fn()
                except Exception as exc:
                    logger.debug("terminate() вызвал ошибку: %s", exc)

            # Проверяем, завершился ли
            if callable(is_running_fn):
                try:
                    if not is_running_fn():
                        return
                except Exception:
                    pass

            if callable(kill_fn):
                try:
                    kill_fn()
                except Exception as exc:
                    logger.debug("kill() вызвал ошибку: %s", exc)

            # Если передан целочисленный PID
            if isinstance(proc, int):
                try:
                    os.kill(proc, 9)
                except OSError:
                    pass
        except Exception as exc:
            logger.warning(
                "Ошибка при принудительном завершении процесса %s: %s", proc, exc
            )

    def _remove_directory(self, path: Path) -> None:
        """Удаляет каталог с retry механизмом для файловых блокировок Windows."""
        for attempt in range(5):
            try:
                shutil.rmtree(path, ignore_errors=False)
                return
            except OSError:
                time.sleep(0.05 * (attempt + 1))
        # Fallback с игнорированием ошибок
        shutil.rmtree(path, ignore_errors=True)

    def _on_lifecycle_shutdown(self) -> None:
        """Callback для аварийного завершения приложения через chutils.lifecycle."""
        logger.warning(
            "LiveBrowserSession: экстренная очистка сессии при shutdown приложения."
        )
        self.cleanup()

    def __enter__(self) -> Self:
        """Вход в контекстный менеджер."""
        ensure_dir(self.user_data_dir)
        self._is_active = True
        register_cleanup(self._on_lifecycle_shutdown)
        self._cleanup_registered = True
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Выход из контекстного менеджера."""
        if exc_val is not None and self.keep_profile_on_failure:
            logger.info(
                "Тест завершился с ошибкой, профиль сохранен для отладки: %s",
                self.user_data_dir,
            )
            self.auto_cleanup_dir = False

        self.cleanup()

    async def __aenter__(self) -> Self:
        """Вход в асинхронный контекстный менеджер."""
        return self.__enter__()

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Выход из асинхронного контекстного менеджера."""
        self.__exit__(exc_type, exc_val, exc_tb)
