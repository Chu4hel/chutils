"""FileBackend — хранение журнала аудита в append-only JSONL файле."""
from __future__ import annotations

import json
import threading
from pathlib import Path

from chutils.audit._hash import compute_record_hash
from chutils.audit.backends.base import BaseAuditBackend
from chutils.fs import ensure_dir


class FileBackend(BaseAuditBackend):
    """Бэкенд хранения событий аудита в JSONL-файле.

    Каждая строка файла — одна запись в формате JSON.
    Записи связаны в криптографическую цепочку через поле prev_hash.
    Запись и вычисление хэшей потокобезопасны.

    Args:
        path: Путь к файлу журнала (будет создан при первой записи).
    """

    def __init__(self, path: str | Path) -> None:
        """Инициализирует FileBackend с указанным путём к файлу журнала.

        Args:
            path: Путь к JSONL-файлу журнала (будет создан при первой записи).
        """
        self._path = Path(path)
        self._lock = threading.Lock()

    def _get_last_hash(self) -> str:
        """Возвращает hash последней записи или '', если файл пуст."""
        if not self._path.exists():
            return ""
        with open(self._path, "rb") as f:
            last_line = b""
            for line in f:
                stripped = line.strip()
                if stripped:
                    last_line = stripped
        if not last_line:
            return ""
        record = json.loads(last_line)
        return str(record.get("hash", ""))

    def log(
            self,
            action: str,
            actor: str,
            *,
            target: str | None = None,
            status: str = "success",
            details: dict[str, object] | None = None,
    ) -> str:
        """Добавляет событие в JSONL-файл.

        Args:
            action: Название операции.
            actor: Субъект действия.
            target: Объект операции (опционально).
            status: Результат — 'success' или 'failed'.
            details: Произвольные детали события.

        Returns:
            UUID созданной записи.
        """
        from chutils.audit.schema import AuditEvent

        with self._lock:
            prev_hash = self._get_last_hash()
            event = AuditEvent(
                actor=actor,
                action=action,
                target=target,
                status=status,
                details=details or {},
                prev_hash=prev_hash,
            )
            ensure_dir(self._path.parent)
            with open(self._path, "a", encoding="utf-8") as f:
                f.write(event.to_jsonl() + "\n")
            return str(event.id)

    def verify_integrity(self) -> bool:
        """Проверяет целостность цепочки хэшей в JSONL-файле.

        Returns:
            True если цепочка не нарушена.

        Raises:
            AuditIntegrityError: При обнаружении повреждённой записи.
        """
        from chutils.exceptions import AuditIntegrityError

        if not self._path.exists():
            return True

        prev_hash = ""
        with open(self._path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                stored_hash = record.get("hash", "")

                expected_hash = compute_record_hash(record)

                if stored_hash != expected_hash:
                    raise AuditIntegrityError(
                        "Нарушена целостность записи: hash не совпадает.",
                        record_id=record.get("id", "unknown"),
                    )
                if record.get("prev_hash", "") != prev_hash:
                    raise AuditIntegrityError(
                        "Нарушена целостность записи: prev_hash не совпадает с предыдущим hash.",
                        record_id=record.get("id", "unknown"),
                    )
                prev_hash = stored_hash

        return True
