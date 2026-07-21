"""
Тесты для модуля уборки мусора разработки (chutils.dev.cleaner и chutils dev clean).
"""
from __future__ import annotations

import argparse
from pathlib import Path
from unittest.mock import patch

import pytest

from chutils.commands.dev.clean import CleanSubCommand
from chutils.dev.cleaner import (
    CleanItem,
    execute_clean,
    get_path_size,
    match_pattern,
    scan_project,
)


def test_clean_item_properties(tmp_path: Path) -> None:
    """Проверяет свойства CleanItem и форматирование размера."""
    item_file = CleanItem(path=tmp_path / "test.txt", size_bytes=500, is_dir=False)
    assert item_file.display_size == "500 B"

    item_kb = CleanItem(path=tmp_path / "test.txt", size_bytes=2048, is_dir=False)
    assert item_kb.display_size == "2.0 KB"

    item_mb = CleanItem(path=tmp_path / "test.txt", size_bytes=1048576 * 5, is_dir=False)
    assert item_mb.display_size == "5.0 MB"


def test_get_path_size(tmp_path: Path) -> None:
    """Проверяет корректность расчета размеров файлов и директорий."""
    # Несуществующий путь
    assert get_path_size(tmp_path / "non_existent") == 0

    # Файл
    f = tmp_path / "file.txt"
    f.write_bytes(b"12345")
    assert get_path_size(f) == 5

    # Директория с файлами
    sub_dir = tmp_path / "dir"
    sub_dir.mkdir()
    (sub_dir / "f1.txt").write_bytes(b"hello")
    (sub_dir / "f2.txt").write_bytes(b"world")
    assert get_path_size(sub_dir) == 10


def test_match_pattern() -> None:
    """Проверяет функции сопоставления шаблонов файлов и папок."""
    assert match_pattern("__pycache__", ["__pycache__"])
    assert match_pattern("test.pyc", ["*.pyc"])
    assert match_pattern(".venv", [".venv/"])
    assert not match_pattern("main.py", ["*.pyc", "__pycache__"])


def test_scan_project(tmp_path: Path) -> None:
    """Проверяет рекурсивное сканирование временных файлов и исключение папок."""
    # Создаем структуру проекта
    pycache = tmp_path / "__pycache__"
    pycache.mkdir()
    (pycache / "compiled.pyc").write_bytes(b"cached")

    venv = tmp_path / ".venv"
    venv.mkdir()
    venv_pycache = venv / "__pycache__"
    venv_pycache.mkdir()
    (venv_pycache / "ignored.pyc").write_bytes(b"ignored")

    extra_file = tmp_path / "custom.log"
    extra_file.write_bytes(b"log data")

    # Сканируем
    items = scan_project(
        base_dir=tmp_path,
        excludes=[".venv"],
        default_targets=["__pycache__", "*.pyc"],
        extra_targets=["*.log"],
    )

    paths = [item.path for item in items]
    assert pycache in paths
    assert extra_file in paths
    assert venv_pycache not in paths


def test_execute_clean(tmp_path: Path) -> None:
    """Проверяет физическое удаление файлов и подсчет освобожденного места."""
    f1 = tmp_path / "junk1.tmp"
    f1.write_bytes(b"1234567890")

    d1 = tmp_path / "junk_dir"
    d1.mkdir()
    (d1 / "file.txt").write_bytes(b"12345")

    items = [
        CleanItem(path=f1, size_bytes=10, is_dir=False),
        CleanItem(path=d1, size_bytes=5, is_dir=True),
    ]

    count, freed = execute_clean(items)
    assert count == 2
    assert freed == 15
    assert not f1.exists()
    assert not d1.exists()


def test_cli_clean_dry_run(tmp_path: Path) -> None:
    """Проверяет CLI команду dev clean в режиме --dry-run."""
    pycache = tmp_path / "__pycache__"
    pycache.mkdir()

    cmd = CleanSubCommand()
    args = argparse.Namespace(
        exclude=None,
        include=None,
        dry_run=True,
        force=False,
    )

    with patch("pathlib.Path.cwd", return_value=tmp_path):
        with pytest.raises(SystemExit) as exc_info:
            cmd.handle(args)
        assert exc_info.value.code == 0

    # Файл должен остаться в режиме dry-run
    assert pycache.exists()


def test_cli_clean_force(tmp_path: Path) -> None:
    """Проверяет CLI команду dev clean с флагом --force / --yes."""
    pycache = tmp_path / "__pycache__"
    pycache.mkdir()

    cmd = CleanSubCommand()
    args = argparse.Namespace(
        exclude=None,
        include=None,
        dry_run=False,
        force=True,
    )

    with patch("pathlib.Path.cwd", return_value=tmp_path):
        with pytest.raises(SystemExit) as exc_info:
            cmd.handle(args)
        assert exc_info.value.code == 0

    assert not pycache.exists()


def test_cli_clean_interactive_decline(tmp_path: Path) -> None:
    """Проверяет отмену очистки при интерактивном вопросе."""
    pycache = tmp_path / "__pycache__"
    pycache.mkdir()

    cmd = CleanSubCommand()
    args = argparse.Namespace(
        exclude=None,
        include=None,
        dry_run=False,
        force=False,
    )

    with patch("pathlib.Path.cwd", return_value=tmp_path), patch("builtins.input", return_value="n"):
        with pytest.raises(SystemExit) as exc_info:
            cmd.handle(args)
        assert exc_info.value.code == 0

    assert pycache.exists()


def test_cli_clean_empty_project(tmp_path: Path) -> None:
    """Проверяет поведение команды dev clean, когда мусорные файлы отсутствуют."""
    cmd = CleanSubCommand()
    args = argparse.Namespace(
        exclude=None,
        include=None,
        dry_run=False,
        force=False,
    )

    with patch("pathlib.Path.cwd", return_value=tmp_path):
        with pytest.raises(SystemExit) as exc_info:
            cmd.handle(args)
        assert exc_info.value.code == 0
