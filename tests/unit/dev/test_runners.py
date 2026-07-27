"""
Тесты для SubprocessRunner и InProcessReloader.
"""

import sys
import time
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from chutils.dev.runners import InProcessReloader, SubprocessRunner
from chutils.lifecycle import register_cleanup

if TYPE_CHECKING:
    from pytest import TempPathFactory


def test_subprocess_runner_lifecycle() -> None:
    """Проверяет запуск, остановку и перезапуск дочернего процесса."""
    # Используем простейшую команду python, спит 10 секунд
    cmd = [sys.executable, "-c", "import time; time.sleep(10)"]
    runner = SubprocessRunner(command=cmd, graceful_timeout=1.0)

    runner.start()
    assert runner.is_running is True
    proc = runner.process
    assert proc is not None and proc.poll() is None

    # Перезапуск процесса
    runner.restart()
    assert runner.is_running is True
    new_proc = runner.process
    assert new_proc is not None and new_proc != proc

    # Остановка процесса
    runner.stop()
    assert runner.is_running is False
    assert new_proc.poll() is not None


def test_subprocess_runner_force_kill() -> None:
    """Проверяет принудительное уничтожение процесса при таймауте SIGTERM."""
    # Процесс игнорирует SIGINT/SIGTERM в блоке try-except (в отдельном python скрипте)
    code = (
        "import signal, time\n"
        "signal.signal(signal.SIGINT, signal.SIG_IGN)\n"
        "try:\n"
        "    signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
        "except AttributeError:\n"
        "    pass\n"
        "while True:\n"
        "    time.sleep(0.1)\n"
    )
    cmd = [sys.executable, "-c", code]
    runner = SubprocessRunner(command=cmd, graceful_timeout=0.2)

    runner.start()
    assert runner.is_running is True

    runner.stop()
    assert runner.is_running is False


def test_in_process_reloader_target_parsing() -> None:
    """Проверяет корректность разбора целевой функции module:func."""
    reloader = InProcessReloader(target="os.path:join")
    assert reloader.module_name == "os.path"
    assert reloader.func_name == "join"


def test_in_process_reloader_execution_and_lifecycle(tmp_path: pytest.TempPathFactory) -> None:
    """Проверяет запуск функции и вызов очистки LifecycleManager при перезагрузке."""
    cleanup_called = []

    def mock_cleanup() -> None:
        cleanup_called.append(True)

    # Регистрируем коллбек в lifecycle
    register_cleanup(mock_cleanup)

    target_func = MagicMock()
    with patch("importlib.import_module") as mock_import:
        mock_mod = MagicMock()
        mock_mod.my_start = target_func
        mock_import.return_value = mock_mod

        reloader = InProcessReloader(target="dummy_module:my_start")
        reloader.start()

        assert target_func.call_count == 1
        assert reloader.is_running is True

        # Перезапуск релоадера должен вызвать очистку и повторно запустить функцию
        reloader.restart()

        assert len(cleanup_called) >= 1
        assert target_func.call_count == 2

        reloader.stop()
        assert reloader.is_running is False
