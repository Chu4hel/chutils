"""
Тесты для моста Async/Qt (src/chutils/qt/asyncio.py).
"""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from chutils.exceptions import OptionalDependencyError
import chutils.qt.shim as shim


def test_async_worker_without_qt() -> None:
    """Проверяет выбрасывание OptionalDependencyError при отсутствии Qt."""
    with patch.object(shim, "QT_BINDING", None):
        from chutils.qt.asyncio import run_async_task
        with pytest.raises(OptionalDependencyError):
            run_async_task(lambda: 42)


def test_qt_async_worker_run_success() -> None:
    """Проверяет успешное выполнение задачи воркером."""
    mock_signals = MagicMock()

    with patch("chutils.qt.asyncio.require_qt"):
        with patch("chutils.qt.asyncio._QtWorkerSignals", return_value=mock_signals):
            from chutils.qt.asyncio import QtAsyncWorker

            async def sample_coro(x: int) -> int:
                await asyncio.sleep(0.01)
                return x * 2

            worker = QtAsyncWorker(sample_coro, 21)
            worker.run()

            mock_signals.started.emit.assert_called_once()
            mock_signals.finished.emit.assert_called_once_with(42)


def test_qt_async_worker_run_sync_callable() -> None:
    """Проверяет выполнение обычной синхронной функции в воркере."""
    mock_signals = MagicMock()

    with patch("chutils.qt.asyncio.require_qt"):
        with patch("chutils.qt.asyncio._QtWorkerSignals", return_value=mock_signals):
            from chutils.qt.asyncio import QtAsyncWorker

            def sync_calc(a: int, b: int) -> int:
                return a + b

            worker = QtAsyncWorker(sync_calc, 10, 20)
            worker.run()

            mock_signals.finished.emit.assert_called_once_with(30)


def test_qt_async_worker_invalid_target() -> None:
    """Проверяет выброс ошибки при передаче неликвидного target."""
    mock_signals = MagicMock()

    with patch("chutils.qt.asyncio.require_qt"):
        with patch("chutils.qt.asyncio._QtWorkerSignals", return_value=mock_signals):
            from chutils.qt.asyncio import QtAsyncWorker

            worker = QtAsyncWorker("not_callable")  # type: ignore
            worker.run()

            mock_signals.error.emit.assert_called_once()


def test_run_async_task_callbacks() -> None:
    """Проверяет привязку коллбэков в run_async_task."""
    mock_signals = MagicMock()
    success_cb = MagicMock()
    error_cb = MagicMock()

    with patch("chutils.qt.asyncio.require_qt"):
        with patch("chutils.qt.asyncio._QtWorkerSignals", return_value=mock_signals):
            from chutils.qt.asyncio import run_async_task

            run_async_task(lambda: 42, on_success=success_cb, on_error=error_cb)

            mock_signals.finished.connect.assert_any_call(success_cb)
            mock_signals.error.connect.assert_any_call(error_cb)


def test_async_to_qt_decorator() -> None:
    """Проверяет работу декоратора async_to_qt."""
    with patch("chutils.qt.asyncio.run_async_task") as mock_run:
        from chutils.qt.asyncio import async_to_qt

        success_mock = MagicMock()

        @async_to_qt(on_success=success_mock)
        def decorated_task(name: str) -> str:
            return f"Hello, {name}"

        decorated_task("World")
        mock_run.assert_called_once()
