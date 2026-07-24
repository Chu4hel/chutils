"""
Интеграция asyncio и фоновых потоков с циклом событий Qt (Async/Qt Bridge).
"""

from __future__ import annotations

import asyncio
import inspect
from typing import Any, Callable, Coroutine, TypeVar

from .shim import QtCore, Signal, require_qt

T = TypeVar("T")


class _QtWorkerSignals(QtCore.QObject if QtCore is not None else object):
    """Сигналы для передачи результатов из фонового потока в поток UI."""

    if Signal is not None:
        started = Signal()
        finished = Signal(object)
        error = Signal(Exception)
        progress = Signal(int, str)
    else:
        started = None
        finished = None
        error = None
        progress = None


class QtAsyncWorker(QtCore.QThread if QtCore is not None else object):
    """QThread для фонового выполнения асинхронных корутин или тяжелых синхронных функций."""

    def __init__(
        self,
        target: Callable[..., Coroutine[Any, Any, T] | T],
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Инициализирует воркер.

        Args:
            target: Асинхронная корутина или синхронная функция для выполнения.
            *args: Позиционные аргументы.
            **kwargs: Именованные аргументы.
        """
        require_qt()
        super().__init__()
        self.target = target
        self.args = args
        self.kwargs = kwargs
        self.signals = _QtWorkerSignals()

    def run(self) -> None:
        """Основной метод потока QThread."""
        try:
            if self.signals and hasattr(self.signals, "started") and self.signals.started:
                self.signals.started.emit()
            if inspect.iscoroutinefunction(self.target):
                result = asyncio.run(self.target(*self.args, **self.kwargs))
            elif callable(self.target):
                result = self.target(*self.args, **self.kwargs)
                if inspect.isawaitable(result):
                    result = asyncio.run(result)
            else:
                raise ValueError("Параметр target должен быть вызываемым объектом.")
            if self.signals and hasattr(self.signals, "finished") and self.signals.finished:
                self.signals.finished.emit(result)
        except Exception as e:
            if self.signals and hasattr(self.signals, "error") and self.signals.error:
                self.signals.error.emit(e)

    def start(self, priority: Any = None) -> None:
        """Запускает выполнение потока.

        Args:
            priority: Приоритет потока Qt.
        """
        if QtCore is not None and hasattr(super(), "start"):
            super().start(priority)
        else:
            self.run()


def run_async_task(
    target: Callable[..., Coroutine[Any, Any, T] | T],
    *args: Any,
    on_success: Callable[[T], None] | None = None,
    on_error: Callable[[Exception], None] | None = None,
    **kwargs: Any,
) -> QtAsyncWorker:
    """Запускает функцию или корутину в фоновом потоке QThread без блокировки UI.

    Args:
        target: Корутина или синхронная функция.
        *args: Аргументы функции.
        on_success: Слот/коллбэк при успешном завершении задачи.
        on_error: Слот/коллбэк при обработке исключения.
        **kwargs: Именованные аргументы функции.

    Returns:
        Экземпляр запущенного QtAsyncWorker.
    """
    require_qt()
    worker = QtAsyncWorker(target, *args, **kwargs)

    if on_success is not None and hasattr(worker.signals, "finished") and worker.signals.finished:
        worker.signals.finished.connect(on_success)
    if on_error is not None and hasattr(worker.signals, "error") and worker.signals.error:
        worker.signals.error.connect(on_error)

    if hasattr(worker.signals, "finished") and worker.signals.finished:
        worker.signals.finished.connect(worker.deleteLater if hasattr(worker, "deleteLater") else lambda res: None)
    if hasattr(worker.signals, "error") and worker.signals.error:
        worker.signals.error.connect(worker.deleteLater if hasattr(worker, "deleteLater") else lambda err: None)

    worker.start()
    return worker


def async_to_qt(
    on_success: Callable[[Any], None] | None = None,
    on_error: Callable[[Exception], None] | None = None,
) -> Callable[[Callable[..., Coroutine[Any, Any, T] | T]], Callable[..., QtAsyncWorker]]:
    """Декоратор для автоматического запуска асинхронной функции в фоновом потоке Qt.

    Args:
        on_success: Коллбэк для успешного результата.
        on_error: Коллбэк для ошибки.

    Returns:
        Декорированная функция, возвращающая QtAsyncWorker.
    """

    def decorator(func: Callable[..., Coroutine[Any, Any, T] | T]) -> Callable[..., QtAsyncWorker]:
        def wrapper(*args: Any, **kwargs: Any) -> QtAsyncWorker:
            return run_async_task(func, *args, on_success=on_success, on_error=on_error, **kwargs)

        return wrapper

    return decorator
