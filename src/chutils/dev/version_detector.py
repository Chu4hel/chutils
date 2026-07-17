"""
Модуль для обнаружения изменений версии пакета chutils с использованием Git истории.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path


def parse_version_from_toml(content: str) -> str | None:
    """Извлекает версию из содержимого TOML-файла.

    Args:
        content: Содержимое файла pyproject.toml.

    Returns:
        Строка с версией или None, если версия не найдена.
    """
    # Ищем version = "..." в секции [project]
    match = re.search(r'(?ms)^\[project\].*?^version\s*=\s*["\']([^"\']+)["\']', content)
    if match:
        return match.group(1)
    # Запасной вариант: поиск первого вхождения version = "..."
    match = re.search(r'^version\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE)
    if match:
        return match.group(1)
    return None


def parse_version_tuple(version_str: str) -> tuple[int, ...]:
    """Преобразует строку версии в кортеж чисел для сравнения.

    Args:
        version_str: Строка версии (например, '3.2.0-dev' или 'v1.0.2').

    Returns:
        Кортеж чисел (например, (3, 2, 0) или (1, 0, 2)).
    """
    version_clean = version_str.lstrip("vV")
    parts: list[int] = []
    for part in version_clean.split("."):
        match = re.match(r"^\d+", part)
        if match:
            parts.append(int(match.group(0)))
        else:
            parts.append(0)
    return tuple(parts)


def get_current_version(base_dir: str) -> str | None:
    """Возвращает текущую версию пакета из pyproject.toml в рабочей директории.

    Args:
        base_dir: Путь к корню проекта.

    Returns:
        Строка версии или None при ошибках.
    """
    path = Path(base_dir) / "pyproject.toml"
    if not path.exists():
        return None
    try:
        content = path.read_text(encoding="utf-8")
        return parse_version_from_toml(content)
    except Exception:
        return None


def get_git_head_version(base_dir: str) -> str | None:
    """Возвращает версию пакета из pyproject.toml в Git HEAD.

    Args:
        base_dir: Путь к корню проекта.

    Returns:
        Строка версии или None при ошибках.
    """
    try:
        result = subprocess.run(
            ["git", "show", "HEAD:pyproject.toml"],
            cwd=base_dir,
            capture_output=True,
            text=True,
            check=True
        )
        return parse_version_from_toml(result.stdout)
    except Exception:
        return None


def detect_version_upgrade(base_dir: str) -> tuple[str | None, str | None, bool]:
    """Проверяет, произошло ли обновление версии в pyproject.toml.

    Сравнивает текущую версию в рабочей директории с версией в Git HEAD.

    Args:
        base_dir: Путь к корню проекта.

    Returns:
        Кортеж (old_version, new_version, is_upgraded).
    """
    old_version = get_git_head_version(base_dir)
    new_version = get_current_version(base_dir)

    if not old_version or not new_version:
        return old_version, new_version, False

    try:
        old_t = parse_version_tuple(old_version)
        new_t = parse_version_tuple(new_version)
        return old_version, new_version, new_t > old_t
    except Exception:
        return old_version, new_version, False
