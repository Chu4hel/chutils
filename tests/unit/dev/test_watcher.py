"""
Тесты для файловых вотчеров (PollingWatcher, WatchdogWatcher, get_watcher).
"""

import os
import time
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from chutils.dev.watcher import (
    BaseWatcher,
    PollingWatcher,
    WatchdogWatcher,
    get_watcher,
)

if TYPE_CHECKING:
    from _pytest.capture import CaptureFixture
    from _pytest.logging import LogCaptureFixture
    from pytest import TempPathFactory


def test_base_watcher_extension_filtering(tmp_path: pytest.TempPathFactory) -> None:
    """Проверяет фильтрацию файлов по расширениям."""
    watcher = PollingWatcher(
        paths=str(tmp_path),
        extensions=["py", "yaml", "json"],
        ignore_patterns=[".git", ".venv"],
    )

    assert watcher._should_process_file("test.py") is True
    assert watcher._should_process_file("config.yaml") is True
    assert watcher._should_process_file("data.json") is True
    assert watcher._should_process_file("readme.md") is False
    assert watcher._should_process_file("app.log") is False


def test_base_watcher_ignore_patterns(tmp_path: pytest.TempPathFactory) -> None:
    """Проверяет фильтрацию файлов по шаблонам игнорирования."""
    watcher = PollingWatcher(
        paths=str(tmp_path),
        extensions=["py"],
        ignore_patterns=[".git", ".venv", "__pycache__", ".pytest_cache"],
    )

    git_path = os.path.join(str(tmp_path), ".git", "config.py")
    venv_path = os.path.join(str(tmp_path), ".venv", "lib", "site.py")
    normal_path = os.path.join(str(tmp_path), "src", "main.py")

    assert watcher._should_process_file(git_path) is False
    assert watcher._should_process_file(venv_path) is False
    assert watcher._should_process_file(normal_path) is True


def test_polling_watcher_detects_file_change(tmp_path: pytest.TempPathFactory) -> None:
    """Проверяет обнаружение изменений файловой системы через PollingWatcher."""
    changed_files_received: list[list[str]] = []

    def on_change(files: list[str]) -> None:
        changed_files_received.append(files)

    test_file = os.path.join(str(tmp_path), "app.py")
    with open(test_file, "w", encoding="utf-8") as f:
        f.write("x = 1")

    watcher = PollingWatcher(
        paths=str(tmp_path),
        extensions=["py"],
        poll_interval=0.1,
        debounce_seconds=0.1,
        callback=on_change,
    )

    watcher.start()
    assert watcher.is_running is True

    try:
        time.sleep(0.15)
        # Изменяем файл
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("x = 2")

        # Ждем срабатывания polling и debounce
        time.sleep(0.4)
        assert len(changed_files_received) >= 1
        flat_files = [f for sublist in changed_files_received for f in sublist]
        assert any("app.py" in f for f in flat_files)
    finally:
        watcher.stop()
        assert watcher.is_running is False


def test_watchdog_watcher_detects_change(tmp_path: pytest.TempPathFactory) -> None:
    """Проверяет работу WatchdogWatcher при доступной библиотеке watchdog."""
    changed_files_received: list[list[str]] = []

    def on_change(files: list[str]) -> None:
        changed_files_received.append(files)

    test_file = os.path.join(str(tmp_path), "main.py")
    with open(test_file, "w", encoding="utf-8") as f:
        f.write("print('hello')")

    watcher = WatchdogWatcher(
        paths=str(tmp_path),
        extensions=["py"],
        debounce_seconds=0.1,
        callback=on_change,
    )

    watcher.start()
    assert watcher.is_running is True

    try:
        time.sleep(0.1)
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("print('world')")

        time.sleep(0.4)
        assert len(changed_files_received) >= 1
    finally:
        watcher.stop()
        assert watcher.is_running is False


def test_get_watcher_fallback(tmp_path: pytest.TempPathFactory, caplog: pytest.LogCaptureFixture) -> None:
    """Проверяет fallback на PollingWatcher с предупреждением при отсутствии watchdog."""
    with patch("chutils.dev.watcher.HAS_WATCHDOG", False):
        watcher = get_watcher(
            paths=str(tmp_path),
            extensions=["py"],
        )
        assert isinstance(watcher, PollingWatcher)
