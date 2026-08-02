"""
Модуль для получения чейнджлогов релизов пакета chutils с GitHub Releases API.
"""
from __future__ import annotations

import json
import logging  # chutils: ignore[ChutilsIntegrationRule]
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

logger = logging.getLogger("chutils.upgrade_client")

CACHE_LIFETIME_SECONDS = 12 * 60 * 60  # 12 часов


def get_cache_paths(base_dir: str) -> tuple[Path, Path]:
    """Возвращает пути к директории кэша и файлу релизов.

    Args:
        base_dir: Путь к корню проекта.

    Returns:
        Кортеж (директория_кэша, файл_кэша).
    """
    cache_dir = Path(base_dir) / ".chutils" / "changelog_cache"
    cache_file = cache_dir / "github_releases.json"
    return cache_dir, cache_file


def _get_installed_version() -> str:
    """Возвращает текущую установленную версию chutils."""
    try:
        from chutils.dev.version_detector import get_current_version
        v = get_current_version(".")
        if v:
            return v
    except Exception:
        pass
    return "unknown"


def load_releases_from_cache(cache_file: Path, ignore_lifetime: bool = False) -> list[dict[str, Any]] | None:
    """Загружает список релизов из локального кэша, если он актуален.

    Args:
        cache_file: Путь к файлу кэша.
        ignore_lifetime: Если True, игнорирует время жизни кэша (используется при ошибках сети).

    Returns:
        Список релизов или None, если кэш невалиден, устарел или версия библиотеки изменилась.
    """
    if not cache_file.exists():
        return None

    try:
        mtime = cache_file.stat().st_mtime
        if not ignore_lifetime and (time.time() - mtime > CACHE_LIFETIME_SECONDS):
            return None

        content = cache_file.read_text(encoding="utf-8")
        data = json.loads(content)
        
        # Поддержка нового формата с метаданными {installed_version, releases}
        if isinstance(data, dict) and "releases" in data:
            cached_version = data.get("installed_version")
            current_version = _get_installed_version()
            if not ignore_lifetime and cached_version != current_version:
                logger.info("Версия chutils изменилась (%s -> %s), кэш чейнджлогов инвалидирован", cached_version, current_version)
                return None
            releases: list[dict[str, Any]] = data["releases"]
            return releases

        # Поддержка старого формата списка для обратной совместимости при обновлении
        if isinstance(data, list):
            legacy_releases: list[dict[str, Any]] = data
            return legacy_releases
    except Exception as e:
        logger.warning("Не удалось прочитать кэш чейнджлогов: %s", e)

    return None


def save_releases_to_cache(cache_dir: Path, cache_file: Path, releases: list[dict[str, Any]]) -> None:
    """Сохраняет список релизов в локальный кэш с метаданными версии.

    Args:
        cache_dir: Директория кэша.
        cache_file: Файл кэша.
        releases: Данные для сохранения.
    """
    try:
        from chutils.fs import ensure_dir, atomic_write
        ensure_dir(cache_dir)
        payload = {
            "installed_version": _get_installed_version(),
            "releases": releases,
        }
        content = json.dumps(payload, ensure_ascii=False, indent=2)
        atomic_write(cache_file, content)
    except Exception as e:
        logger.warning("Не удалось сохранить кэш чейнджлогов: %s", e)


def fetch_changelogs(base_dir: str, repo: str = "Chu4hel/chutils") -> list[dict[str, Any]]:
    """Получает список релизов с описаниями из GitHub API с поддержкой кэширования.

    Args:
        base_dir: Путь к корню проекта.
        repo: Имя репозитория на GitHub (по умолчанию 'Chu4hel/chutils').

    Returns:
        Список словарей с описанием релизов.
    """
    cache_dir, cache_file = get_cache_paths(base_dir)

    # 1. Попытка загрузить свежий кэш
    releases = load_releases_from_cache(cache_file)
    if releases is not None:
        return releases

    # 2. Запрос к GitHub Releases API
    url = f"https://api.github.com/repos/{repo}/releases"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "chutils-upgrade-client",
            "Accept": "application/vnd.github.v3+json",
        }
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            content = response.read().decode("utf-8")
            data = json.loads(content)
            if isinstance(data, list):
                # Сохраняем в кэш
                save_releases_to_cache(cache_dir, cache_file, data)
                return data
    except Exception as e:
        logger.warning("Не удалось получить релизы из GitHub API (%s). Попытка загрузить устаревший кэш...", e)

    # 3. Резервный вариант: чтение любого (даже устаревшего) кэша при ошибках сети
    releases = load_releases_from_cache(cache_file, ignore_lifetime=True)
    if releases is not None:
        return releases

    return []
