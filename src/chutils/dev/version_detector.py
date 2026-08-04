"""
Модуль для обнаружения изменений версии пакета chutils с использованием Git истории.
Поддерживает различные форматы проектов (pyproject.toml, requirements.txt, Pipfile)
и lock-файлы (uv.lock, poetry.lock, Pipfile.lock).
"""
from __future__ import annotations

import importlib.metadata
import json
import re
import subprocess
from pathlib import Path

LOCK_FILES = ["uv.lock", "poetry.lock", "Pipfile.lock", "requirements.lock"]
"""Список поддерживаемых lock-файлов в порядке приоритета."""

MANIFEST_FILES = ["pyproject.toml", "requirements.txt", "Pipfile"]
"""Список поддерживаемых файлов манифестов проектов."""


def clean_version_specifier(spec: str) -> str | None:
    """Извлекает чистый номер версии из строки спецификации зависимости.

    Args:
        spec: Строка спецификации (например, '>=3.2.0', '^1.0.0', '==2.5.1', 'chutils (>=3.2.0)').

    Returns:
        Чистая строка версии (например, '3.2.0') или None.
    """
    if not spec:
        return None
    match = re.search(r"v?(\d+(?:\.\d+)+(?:-[a-zA-Z0-9.]+)?)" , spec)
    if match:
        return match.group(1)
    return None


def parse_chutils_from_pyproject(content: str) -> str | None:
    """Извлекает версию пакета chutils из pyproject.toml.

    Если текущий проект — сам chutils (name = "chutils" в [project]),
    извлекается версия самого проекта. В противном случае извлекается
    версия зависимости chutils из секций dependencies.

    Args:
        content: Содержимое файла pyproject.toml.

    Returns:
        Строка версии chutils или None.
    """
    # 1. Проверяем, является ли текущий проект репозиторием chutils
    is_chutils_repo = bool(
        re.search(r'(?ms)^\[project\].*?^name\s*=\s*["\']chutils["\']', content)
    )
    if is_chutils_repo:
        match = re.search(r'(?ms)^\[project\].*?^version\s*=\s*["\']([^"\']+)["\']', content)
        if match:
            return clean_version_specifier(match.group(1))

    # 2. Ищем chutils в секциях зависимостей Poetry: chutils = "^3.2.0" или chutils = { version = "3.2.0" }
    poetry_match = re.search(r'^chutils\s*=\s*(.+)$', content, re.MULTILINE)
    if poetry_match:
        v = clean_version_specifier(poetry_match.group(1))
        if v:
            return v

    # 3. Ищем chutils в списках зависимостей PEP 621 / hatch / setuptools: "chutils>=3.2.0"
    dep_match = re.search(r'["\']chutils([^"\']*)["\']', content)
    if dep_match:
        v = clean_version_specifier(dep_match.group(1))
        if v:
            return v

    return None


def parse_chutils_from_lockfile(filename: str, content: str) -> str | None:
    """Извлекает версию chutils из lock-файла (uv.lock, poetry.lock, Pipfile.lock).

    Args:
        filename: Имя lock-файла.
        content: Содержимое файла.

    Returns:
        Строка версии или None.
    """
    fname = filename.lower()

    if fname.endswith(".json") or "pipfile.lock" in fname:
        try:
            data = json.loads(content)
            for section in ["default", "develop"]:
                if section in data and "chutils" in data[section]:
                    pkg = data[section]["chutils"]
                    if isinstance(pkg, dict) and "version" in pkg:
                        return clean_version_specifier(str(pkg["version"]))
                    elif isinstance(pkg, str):
                        return clean_version_specifier(pkg)
        except Exception:
            pass

        match = re.search(r'"chutils"\s*:\s*\{[^}]*"version"\s*:\s*"([^"]+)"', content)
        if match:
            return clean_version_specifier(match.group(1))

    # TOML lock-файлы (uv.lock, poetry.lock)
    match = re.search(r'(?ms)\[\[package\]\]\s*name\s*=\s*["\']chutils["\'].*?version\s*=\s*["\']([^"\']+)["\']', content)
    if match:
        return clean_version_specifier(match.group(1))

    match_rev = re.search(r'(?ms)\[\[package\]\]\s*version\s*=\s*["\']([^"\']+)["\'].*?name\s*=\s*["\']chutils["\']', content)
    if match_rev:
        return clean_version_specifier(match_rev.group(1))

    return None


def parse_chutils_from_requirements(content: str) -> str | None:
    """Извлекает версию chutils из файла требований (requirements.txt, Pipfile и др.).

    Args:
        content: Содержимое файла требований.

    Returns:
        Строка версии или None.
    """
    for line in content.splitlines():
        line_str = line.strip()
        if not line_str or line_str.startswith("#"):
            continue
        if "chutils" in line_str:
            v = clean_version_specifier(line_str)
            if v:
                return v
    return None


def parse_version_from_toml(content: str) -> str | None:
    """Извлекает версию из содержимого TOML-файла.

    Args:
        content: Содержимое файла pyproject.toml.

    Returns:
        Строка с версией или None, если версия не найдена.
    """
    version = parse_chutils_from_pyproject(content)
    if version:
        return version

    match = re.search(r'(?ms)^\[project\].*?^version\s*=\s*["\']([^"\']+)["\']', content)
    if match:
        return clean_version_specifier(match.group(1))
    match = re.search(r'^version\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE)
    if match:
        return clean_version_specifier(match.group(1))
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
    """Возвращает текущую версию пакета chutils в рабочей директории.

    Args:
        base_dir: Путь к корню проекта.

    Returns:
        Строка версии или None при ошибках.
    """
    base_path = Path(base_dir)

    # 1. Проверяем lock-файлы (наивысший приоритет — точные зафиксированные версии)
    for lock_name in LOCK_FILES:
        lock_path = base_path / lock_name
        if lock_path.exists():
            try:
                content = lock_path.read_text(encoding="utf-8")
                v = parse_chutils_from_lockfile(lock_name, content)
                if v:
                    return v
            except Exception:
                pass

    # 2. Проверяем манифесты (pyproject.toml, requirements.txt, Pipfile)
    pyproject_path = base_path / "pyproject.toml"
    if pyproject_path.exists():
        try:
            content = pyproject_path.read_text(encoding="utf-8")
            v = parse_chutils_from_pyproject(content)
            if v:
                return v
        except Exception:
            pass

    for manifest_name in ["requirements.txt", "Pipfile"]:
        manifest_path = base_path / manifest_name
        if manifest_path.exists():
            try:
                content = manifest_path.read_text(encoding="utf-8")
                v = parse_chutils_from_requirements(content)
                if v:
                    return v
            except Exception:
                pass

    # 3. Резервный вариант: версия установленного chutils в окружении Python
    try:
        return importlib.metadata.version("chutils")
    except Exception:
        return None


def get_git_head_version(base_dir: str) -> str | None:
    """Возвращает версию пакета chutils в Git HEAD.

    Args:
        base_dir: Путь к корню проекта.

    Returns:
        Строка версии или None при ошибках.
    """
    all_target_files = LOCK_FILES + MANIFEST_FILES
    for filename in all_target_files:
        try:
            result = subprocess.run(
                ["git", "show", f"HEAD:{filename}"],
                cwd=base_dir,
                capture_output=True,
                text=True,
                check=True
            )
            content = result.stdout
            if not content:
                continue

            if filename.endswith(".lock"):
                v = parse_chutils_from_lockfile(filename, content)
            elif filename == "pyproject.toml":
                v = parse_chutils_from_pyproject(content)
            else:
                v = parse_chutils_from_requirements(content)

            if v:
                return v
        except Exception:
            continue

    return None


def get_last_known_version(base_dir: str) -> str | None:
    """Возвращает зафиксированную последнюю известную версию chutils из .chutils/last_known_version.json.

    Args:
        base_dir: Путь к корню проекта.

    Returns:
        Строка версии или None.
    """
    path = Path(base_dir) / ".chutils" / "last_known_version.json"
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                val = data.get("installed_version")
                if isinstance(val, str):
                    return val
        except Exception:
            pass
    return None


def save_last_known_version(base_dir: str, version: str) -> None:
    """Сохраняет текущую зафиксированную версию chutils в .chutils/last_known_version.json.

    Args:
        base_dir: Путь к корню проекта.
        version: Строка версии.
    """
    try:
        from chutils.fs import ensure_dir

        path = Path(base_dir) / ".chutils" / "last_known_version.json"
        ensure_dir(path.parent)
        path.write_text(json.dumps({"installed_version": version}, indent=2), encoding="utf-8")
    except Exception:
        pass


def detect_version_upgrade(base_dir: str) -> tuple[str | None, str | None, bool]:
    """Проверяет, произошло ли обновление версии chutils в проекте.

    Сравнивает текущую версию в рабочей директории с зафиксированной исторической
    версией из .chutils/last_known_version.json и версии в Git HEAD.

    Args:
        base_dir: Путь к корню проекта.

    Returns:
        Кортеж (old_version, new_version, is_upgraded).
    """
    head_version = get_git_head_version(base_dir)
    stored_version = get_last_known_version(base_dir)
    new_version = get_current_version(base_dir)

    old_version = stored_version or head_version

    # Если есть и зафиксированная версия, и HEAD, выберем наименьшую (наиболее раннюю),
    # чтобы не упустить релизы при множественных коммитах во время обновления
    if stored_version and head_version:
        try:
            st_t = parse_version_tuple(stored_version)
            hd_t = parse_version_tuple(head_version)
            if st_t < hd_t:
                old_version = stored_version
            else:
                old_version = head_version
        except Exception:
            pass

    if not old_version or not new_version:
        return old_version, new_version, False

    try:
        old_t = parse_version_tuple(old_version)
        new_t = parse_version_tuple(new_version)
        return old_version, new_version, new_t > old_t
    except Exception:
        return old_version, new_version, False
