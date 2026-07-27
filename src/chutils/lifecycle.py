"""
Управление жизненным циклом приложения.

Обеспечивает механизмы регистрации функций очистки (cleanup callbacks), 
которые будут выполнены при завершении работы приложения.
"""

from __future__ import annotations

import asyncio
import inspect
import logging  # chutils: ignore[ChutilsIntegrationRule]
import signal
import sys
import time
from collections.abc import Callable, Awaitable
from typing import Union, Any, TYPE_CHECKING, cast

from chutils.config import get_config_int

if TYPE_CHECKING:
    from types import FrameType

logger = logging.getLogger(__name__)

# Тип для функций очистки: может быть обычной функцией или корутиной
CleanupCallback = Union[Callable[[], Any], Callable[[], Awaitable[Any]]]


class LifecycleManager:
    """
    Менеджер жизненного цикла, управляющий реестром функций очистки.
    """

    def __init__(self) -> None:
        """Инициализирует LifecycleManager."""
        self._cleanup_callbacks: list[CleanupCallback] = []
        self._is_shutting_down = False
        self._setup_done = False

    def register_cleanup(self, func: CleanupCallback) -> CleanupCallback:
        """
        Регистрирует функцию для выполнения при завершении работы.

        Функции выполняются в порядке LIFO (Last-In-First-Out).
        Поддерживаются как синхронные, так и асинхронные функции.

        Args:
            func: Функция или корутина для регистрации.

        Returns:
            Та же функция (позволяет использовать как декоратор).
        """
        if func not in self._cleanup_callbacks:
            self._cleanup_callbacks.append(func)
            logger.debug("Зарегистрирована функция очистки: %s",
                         func.__name__ if hasattr(func, '__name__') else str(func))
        return func

    def get_cleanup_callbacks(self) -> list[CleanupCallback]:
        """Возвращает список зарегистрированных функций в порядке LIFO.

        Returns:
            Список функций очистки в порядке LIFO.
        """
        return list(reversed(self._cleanup_callbacks))

    def setup_graceful_shutdown(self, signals: list[int] | None = None) -> None:
        """Настраивает перехват сигналов завершения работы.

        Args:
            signals: Опциональный список сигналов для отслеживания.
        """
        if self._setup_done:
            return

        target_signals: list[int] = []
        if signals is None:
            # Выбираем доступные сигналы в зависимости от платформы
            for sig_name in ("SIGINT", "SIGTERM", "SIGHUP"):
                if hasattr(signal, sig_name):
                    target_signals.append(cast(int, getattr(signal, sig_name)))
        else:
            target_signals = signals

        for sig in target_signals:
            try:
                signal.signal(sig, self._handle_signal)
            except (ValueError, RuntimeError) as e:
                logger.warning("Не удалось установить обработчик для сигнала %s: %s", sig, e)

        self._setup_done = True
        logger.debug("Настроен Graceful Shutdown для сигналов: %s", target_signals)

    def _handle_signal(self, signum: int, frame: FrameType | None) -> None:
        """
        Обработчик сигнала ОС.
        """
        try:
            sig_name = signal.Signals(signum).name
        except ValueError:
            sig_name = str(signum)

        logger.info("Получен сигнал %s (%s). Запускается процесс завершения работы...", signum, sig_name)

        if self._is_shutting_down:
            logger.warning("Процесс завершения уже запущен. Повторный сигнал игнорируется.")
            return

        self._run_cleanup()
        sys.exit(128 + signum)

    def _run_cleanup(self) -> None:
        """
        Запускает выполнение всех зарегистрированных функций очистки.
        """
        self._is_shutting_down = True

        # Получаем таймаут из конфига или используем 10 секунд по умолчанию
        timeout = get_config_int("shutdown", "timeout", 10)

        callbacks = self.get_cleanup_callbacks()
        if not callbacks:
            logger.debug("Реестр функций очистки пуст.")
            return

        logger.info("Выполнение функций очистки (%d)...", len(callbacks))

        try:
            # Пытаемся получить текущую петлю событий
            asyncio.get_running_loop()
            # В асинхронном приложении мы не можем использовать asyncio.run()
            # Но так как мы находимся в обработчике сигнала (синхронном),
            # мы запускаем корутину и ждем ее завершения (если это возможно)
            # или полагаемся на asyncio.run ниже, если петля не запущена.
            # На практике, обработчик сигнала часто вызывается вне контекста петли.
            raise RuntimeError("Force fallback to asyncio.run for simplicity in signal handler")
        except RuntimeError:
            # Если петля не запущена или мы решили использовать asyncio.run
            asyncio.run(self._execute_all(callbacks, float(timeout)))

    async def _execute_all(self, callbacks: list[CleanupCallback], timeout: float) -> None:
        """
        Асинхронно выполняет все коллбэки с учетом общего таймаута.
        """
        start_time = time.time()

        for func in callbacks:
            elapsed = time.time() - start_time
            if elapsed >= timeout:
                logger.error("Превышен таймаут очистки (%ds). Оставшиеся функции не будут выполнены.", timeout)
                break

            try:
                if inspect.iscoroutinefunction(func):
                    await cast(Awaitable[Any], func())
                else:
                    # Выполняем синхронную функцию
                    cast(Callable[[], Any], func)()
                logger.debug("Успешно выполнена очистка: %s",
                             func.__name__ if hasattr(func, '__name__') else str(func))
            except Exception as e:
                logger.error("Ошибка при выполнении функции очистки %s: %s",
                             func.__name__ if hasattr(func, '__name__') else str(func), e, exc_info=True)

    def _clear_registry(self) -> None:
        """
        Очищает реестр (в основном для тестов).
        """
        self._cleanup_callbacks.clear()
        self._is_shutting_down = False
        self._setup_done = False


_manager = LifecycleManager()
"Глобальный экземпляр менеджера"


def register_cleanup(func: CleanupCallback) -> CleanupCallback:
    """Регистрирует функцию очистки в менеджере.

    Эта функция является публичным API для добавления колбэков, которые
    будут вызваны при завершении работы приложения.

    Args:
        func: Функция-колбэк, которую нужно зарегистрировать.
            Должна соответствовать типу CleanupCallback.

    Returns:
        Зарегистрированная функция (возвращает тот же объект для
        использования в качестве декоратора).

    Example:
        Использование в качестве декоратора:
            @register_cleanup
            async def close_db():
                await db.close()

        Использование как обычной функции:
            def cleanup_logs():
                print("Cleaning up logs...")
            register_cleanup(cleanup_logs)
    """
    return _manager.register_cleanup(func)


def setup_graceful_shutdown() -> None:
    """
    Публичный API для настройки Graceful Shutdown.

    Рекомендуется вызывать в самом начале работы приложения.
    """
    _manager.setup_graceful_shutdown()


def run_cleanup() -> None:
    """
    Выполняет все зарегистрированные функции очистки LIFO.
    """
    _manager._run_cleanup()
