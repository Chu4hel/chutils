"""
chutils.dev.cleaner — Модуль для сканирования и безопасной уборки мусора разработки.
"""
from __future__ import annotations

import fnmatch
import logging  # chutils: ignore[ChutilsIntegrationRule]
import os
from dataclasses import dataclass
from pathlib import Path

from chutils.fs import remove_path

logger = logging.getLogger(__name__)  # chutils: ignore[ChutilsIntegrationRule]


@dataclass
class CleanItem:
    """Элемент, предназначенный для очистки."""

    path: Path
    size_bytes: int
    is_dir: bool

    @property
    def display_size(self) -> str:
        """Возвращает человекочитаемый размер элемента."""
        size = float(self.size_bytes)
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024.0:
                return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
            size /= 1024.0
        return f"{size:.1f} TB"


def get_path_size(path: Path) -> int:
    """Вычисляет суммарный размер файла или директории в байтах.

    Args:
        path: Путь к файлу или директории.

    Returns:
        Размер в байтах.
    """
    if not path.exists():
        return 0
    if path.is_file() or path.is_symlink():
        try:
            return path.stat().st_size
        except OSError:
            return 0

    total_size = 0
    try:
        for root, _, files in os.walk(path):
            for f in files:
                fp = Path(root) / f
                try:
                    if not fp.is_symlink():
                        total_size += fp.stat().st_size
                except OSError:
                    pass
    except OSError:
        pass
    return total_size


def match_pattern(name: str, patterns: list[str]) -> bool:
    """Проверяет, соответствует ли имя файла/папки хотя бы одному из шаблонов.

    Args:
        name: Имя файла или директории.
        patterns: Список шаблонов (глобов или фиксированных имен).

    Returns:
        True, если имя совпадает с хотя бы одним шаблоном, иначе False.
    """
    for pattern in patterns:
        if pattern.endswith("/"):
            clean_pattern = pattern[:-1]
            if name == clean_pattern or fnmatch.fnmatch(name, clean_pattern):
                return True
        elif fnmatch.fnmatch(name, pattern) or name == pattern:
            return True
    return False


def scan_project(
    base_dir: str | Path,
    excludes: list[str] | None = None,
    default_targets: list[str] | None = None,
    extra_targets: list[str] | None = None,
) -> list[CleanItem]:
    """Сканирует проект и возвращает список найденных временных файлов и папок.

    Args:
        base_dir: Корневая директория проекта.
        excludes: Список папок или шаблонов для исключения из обхода.
        default_targets: Базовый список шаблонов временных файлов/папок.
        extra_targets: Дополнительные шаблоны для очистки.

    Returns:
        Список объектов CleanItem.
    """
    base_path = Path(base_dir).resolve()
    if not base_path.exists():
        return []

    # Загружаем параметры из конфигурации, если они не заданы явно
    if excludes is None or default_targets is None or extra_targets is None:
        try:
            from chutils.config.dev import load_clean_config

            cfg = load_clean_config()
            if excludes is None:
                raw_ex = cfg.get("default_excludes", [])
                excludes = list(raw_ex) if isinstance(raw_ex, list) else []
            if default_targets is None:
                raw_tg = cfg.get("default_targets", [])
                default_targets = list(raw_tg) if isinstance(raw_tg, list) else []
            if extra_targets is None:
                raw_ext = cfg.get("extra_clean_targets", [])
                extra_targets = list(raw_ext) if isinstance(raw_ext, list) else []
        except Exception:
            pass

    exclude_patterns = excludes or [
        ".git",
        ".venv",
        "venv",
        "env",
        ".chutils",
        ".idea",
        ".vscode",
        "site",
        "node_modules",
    ]

    target_patterns = list(
        default_targets
        or [
            "__pycache__",
            "*.pyc",
            "*.pyo",
            "*.pyd",
            ".pytest_cache",
            ".mypy_cache",
            ".ruff_cache",
            ".coverage",
            "htmlcov",
            "build",
            "dist",
            "*.egg-info",
            "*.egg",
        ]
    )

    if extra_targets:
        target_patterns.extend(extra_targets)

    found_items: list[CleanItem] = []
    visited_paths: set[Path] = set()

    for root, dirs, files in os.walk(base_path, topdown=True):
        root_path = Path(root)

        # Исключаем директории из обхода
        dirs[:] = [d for d in dirs if not match_pattern(d, exclude_patterns)]

        dirs_to_remove: list[str] = []
        for d in dirs:
            dir_path = root_path / d
            if match_pattern(d, target_patterns):
                if dir_path not in visited_paths:
                    visited_paths.add(dir_path)
                    size = get_path_size(dir_path)
                    found_items.append(
                        CleanItem(path=dir_path, size_bytes=size, is_dir=True)
                    )
                dirs_to_remove.append(d)

        # Не заглубляемся в мусорные директории
        for d in dirs_to_remove:
            dirs.remove(d)

        # Проверяем файлы
        for f in files:
            file_path = root_path / f
            if match_pattern(f, target_patterns):
                if file_path not in visited_paths:
                    visited_paths.add(file_path)
                    size = get_path_size(file_path)
                    found_items.append(
                        CleanItem(path=file_path, size_bytes=size, is_dir=False)
                    )

    return found_items


def execute_clean(items: list[CleanItem]) -> tuple[int, int]:
    """Удаляет найденные мусорные элементы.

    Args:
        items: Список элементов CleanItem для удаления.

    Returns:
        Кортеж (количество удаленных элементов, суммарно освобожденный размер в байтах).
    """
    removed_count = 0
    freed_bytes = 0

    for item in items:
        try:
            if item.path.exists():
                remove_path(item.path)
                removed_count += 1
                freed_bytes += item.size_bytes
        except Exception as exc:
            logger.warning("Не удалось удалить %s: %s", item.path, exc)

    return removed_count, freed_bytes
