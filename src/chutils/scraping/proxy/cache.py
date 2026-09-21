"""
Модуль дискового кэширования для подсистемы прокси chutils.
"""

from __future__ import annotations

import json
from pathlib import Path
import threading
import time

from chutils import setup_logger
from chutils.cache.base import BaseCacheBackend
from chutils.fs import atomic_write, ensure_dir

logger = setup_logger(__name__)


class FileCacheBackend(BaseCacheBackend[str]):
    """Дисковый кэш строковых значений с поддержкой TTL и атомарной записью через chutils.fs."""

    def __init__(self, file_path: Path | str) -> None:
        """Инициализирует дисковый файловый кэш.

        Args:
            file_path: Путь к целевому JSON-файлу на диске.
        """
        self.file_path = Path(file_path).resolve()
        self._lock = threading.RLock()
        self._data: dict[str, dict[str, object]] = {}
        self._load()

    def _load(self) -> None:
        """Загружает данные из файла кэша."""
        with self._lock:
            if self.file_path.exists():
                try:
                    raw = self.file_path.read_text(encoding="utf-8")
                    parsed = json.loads(raw)
                    if isinstance(parsed, dict):
                        self._data = parsed
                except Exception as exc:
                    logger.warning("Ошибка чтения дискового кэша прокси %s: %s", self.file_path, exc)
                    self._data = {}
            else:
                self._data = {}

    def _save(self) -> None:
        """Атомарно сохраняет словарь на диск."""
        with self._lock:
            try:
                ensure_dir(self.file_path.parent)
                atomic_write(self.file_path, self._data, indent=2)
            except Exception as exc:
                logger.error("Ошибка сохранения дискового кэша прокси %s: %s", self.file_path, exc)

    def get(self, key: str) -> str | None:
        """Возвращает значение из кэша с проверкой срока жизни.

        Args:
            key: Ключ для поиска.

        Returns:
            Строковое значение или None, если запись отсутствует или просрочена.
        """
        with self._lock:
            entry = self._data.get(key)
            if not isinstance(entry, dict):
                return None
            expires_at = entry.get("expires_at")
            if isinstance(expires_at, (int, float)) and time.time() > expires_at:
                del self._data[key]
                self._save()
                return None
            val = entry.get("value")
            return str(val) if val is not None else None

    def set(
        self,
        key: str,
        value: str,
        ttl: int | None = None,
        tags: list[str] | None = None,
    ) -> None:
        """Сохраняет значение в кэше с опциональным TTL.

        Args:
            key: Ключ для сохранения.
            value: Сохраняемое строковое значение.
            ttl: Время жизни записи в секундах.
            tags: Опциональный список тегов.
        """
        with self._lock:
            expires_at = (time.time() + ttl) if ttl is not None else None
            self._data[key] = {
                "value": value,
                "expires_at": expires_at,
                "tags": tags or [],
                "updated_at": time.time(),
            }
            self._save()

    def delete(self, key: str) -> None:
        """Удаляет ключ из кэша.

        Args:
            key: Удаляемый ключ.
        """
        with self._lock:
            if key in self._data:
                del self._data[key]
                self._save()

    def exists(self, key: str) -> bool:
        """Проверяет наличие непросроченного ключа в кэше.

        Args:
            key: Проверяемый ключ.

        Returns:
            True, если ключ найден и не просрочен, иначе False.
        """
        return self.get(key) is not None

    def clear(self) -> None:
        """Полностью очищает кэш."""
        with self._lock:
            self._data.clear()
            self._save()

    def invalidate_tag(self, tag: str) -> None:
        """Инвалидирует все ключи с заданным тегом.

        Args:
            tag: Название тега для очистки.
        """
        with self._lock:
            to_del = [
                k
                for k, v in self._data.items()
                if isinstance(v, dict) and isinstance(tags := v.get("tags"), (list, tuple, set)) and tag in tags
            ]
            for k in to_del:
                del self._data[k]
            if to_del:
                self._save()
