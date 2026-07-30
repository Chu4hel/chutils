"""
Утилиты для сбора метаданных и вычисления хэша проекта.
"""
from __future__ import annotations

import datetime
import subprocess
from pathlib import Path
from typing import Any


def calculate_project_hash(project_path: Path) -> str:
    """Вычисляет детерминированный SHA-256 хэш проекта по содержимому всех python-файлов.

    Args:
        project_path: Путь к корню проекта.

    Returns:
        Строка с SHA-256 хэшем в hex-формате.
    """
    import hashlib
    # Импортируем внутри функции во избежание круговых импортов
    from chutils.dev.ast_indexer import GitIgnoreMatcher
    matcher = GitIgnoreMatcher(project_path)

    py_files: list[Path] = []

    def _collect_files(dir_path: Path) -> None:
        try:
            for item in dir_path.iterdir():
                rel_path = item.relative_to(project_path)
                if matcher.matches(str(rel_path)):
                    continue
                if item.is_dir():
                    _collect_files(item)
                elif item.is_file() and item.suffix == ".py":
                    py_files.append(item)
        except Exception:
            pass

    _collect_files(project_path)
    py_files.sort(key=lambda p: p.relative_to(project_path).as_posix())

    hasher = hashlib.sha256()
    for f in py_files:
        rel_posix = f.relative_to(project_path).as_posix()
        hasher.update(rel_posix.encode("utf-8"))
        try:
            with open(f, "rb") as fh:
                hasher.update(fh.read())
        except Exception:
            pass

    return hasher.hexdigest()


def collect_project_metadata(project_path: Path) -> dict[str, Any]:
    """Собирает метаданные о проекте (версия chutils, версия проекта, git commit, дата, хэш).

    Args:
        project_path: Путь к корню проекта.

    Returns:
        Словарь с собранными метаданными.
    """
    import chutils

    # Находим корень репозитория/проекта (где лежит pyproject.toml или .git)
    real_root = project_path.resolve()
    for parent in [real_root] + list(real_root.parents):
        if (parent / "pyproject.toml").exists() or (parent / ".git").exists():
            real_root = parent
            break

    # Вспомогательная функция парсинга версии
    def _get_version_from_pyproject(toml_path: Path) -> str:
        if not toml_path.exists():
            return "unknown"
        try:
            import tomllib
            with open(toml_path, "rb") as f:
                data = tomllib.load(f)
                if isinstance(data, dict):
                    version = data.get("project", {}).get("version")
                    if version:
                        return str(version)
                    version = data.get("tool", {}).get("poetry", {}).get("version")
                    if version:
                        return str(version)
        except Exception:
            try:
                with open(toml_path, encoding="utf-8") as f:
                    content = f.read()
                for line in content.splitlines():
                    line = line.strip()
                    if line.startswith("version") and "=" in line:
                        parts = line.split("=", 1)
                        val = parts[1].strip().strip("'\"")
                        if val:
                            return val
            except Exception:
                pass
        return "unknown"

    # 1. Версия chutils
    chutils_version = getattr(chutils, "__version__", "unknown")
    if chutils_version == "unknown":
        try:
            import importlib.metadata
            chutils_version = importlib.metadata.version("chutils")
        except Exception:
            pass

    if chutils_version == "unknown":
        try:
            chutils_root = Path(chutils.__file__).parent.parent.parent
            chutils_version = _get_version_from_pyproject(chutils_root / "pyproject.toml")
        except Exception:
            pass

    # 2. Версия целевого проекта
    project_version = _get_version_from_pyproject(real_root / "pyproject.toml")

    # 3. Git commit SHA-1
    git_commit = "unknown"
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(real_root),
            capture_output=True,
            text=True,
            check=True
        )
        git_commit = res.stdout.strip()

        status_res = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(real_root),
            capture_output=True,
            text=True,
            check=True
        )
        if status_res.stdout.strip():
            git_commit += " (dirty)"
    except Exception:
        pass

    # 4. ISO 8601 timestamp
    generated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # 5. Хэш проекта
    project_hash = calculate_project_hash(real_root)

    return {
        "chutils_version": chutils_version,
        "project_version": project_version,
        "git_commit": git_commit,
        "generated_at": generated_at,
        "project_hash": project_hash,
    }


def save_context_metadata_cache(project_path: Path, output_file: str, format_str: str, project_hash: str) -> None:
    """Сохраняет кэш метаданных сгенерированного контекста в .chutils/context_metadata.json.

    Файл хранит реестр ВСЕХ сгенерированных файлов контекста проекта.
    При каждом вызове обновляется только запись для конкретного output_file —
    остальные записи сохраняются.

    Формат файла::

        {
          "files": {
            "api_map.md":         {"format": "markdown", "project_hash": "..."},
            "project_index.json": {"format": "tree",     "project_hash": "..."},
            "docs/context.json":  {"format": "json",     "project_hash": "..."}
          }
        }

    Старый однофайловый формат автоматически мигрируется при первом обращении.

    Args:
        project_path: Корневой путь проекта.
        output_file: Выходной путь файла контекста.
        format_str: Формат вывода ('markdown', 'json' или 'tree').
        project_hash: Сгенерированный хэш проекта.
    """
    import json
    import sys
    if "pytest" in sys.modules:
        # Не пишем на реальный диск из тестов
        if "pytest-" in str(output_file) or "Temp" in str(output_file) or "temp" in str(output_file) or "tmp" in str(
                output_file):
            if "pytest-" not in str(project_path) and "Temp" not in str(project_path) and "temp" not in str(
                    project_path) and "tmp" not in str(project_path):
                return

    chutils_dir = project_path / ".chutils"
    try:
        chutils_dir.mkdir(exist_ok=True)
        cache_path = chutils_dir / "context_metadata.json"

        try:
            rel_path = Path(output_file).resolve().relative_to(project_path.resolve())
            file_path_str = rel_path.as_posix()
        except ValueError:
            file_path_str = output_file

        # Читаем существующий реестр (с автоматической миграцией старого формата)
        files_registry: dict[str, dict[str, str]] = {}
        if cache_path.exists():
            try:
                with open(cache_path, encoding="utf-8") as f:
                    existing = json.load(f)
                if isinstance(existing, dict):
                    if "files" in existing and isinstance(existing["files"], dict):
                        # Текущий многофайловый формат
                        files_registry = existing["files"]
                    elif "file_path" in existing:
                        # Старый однофайловый формат — мигрируем запись
                        old_fp = existing.get("file_path", "")
                        if old_fp:
                            files_registry[old_fp] = {
                                "format": str(existing.get("format", "markdown")),
                                "project_hash": str(existing.get("project_hash", "")),
                            }
            except Exception:
                pass

        # Обновляем только запись для текущего файла, остальные не трогаем
        files_registry[file_path_str] = {
            "format": format_str,
            "project_hash": project_hash,
        }

        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump({"files": files_registry}, f, indent=2, ensure_ascii=False)  # chutils: ignore[ChutilsIntegrationRule]
    except Exception:
        pass

