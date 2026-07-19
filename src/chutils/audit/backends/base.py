"""Абстрактный базовый класс для бэкендов хранения журнала аудита."""
from __future__ import annotations

from abc import ABC, abstractmethod


class BaseAuditBackend(ABC):
    """Абстракция хранилища записей аудита.

    Все бэкенды должны реализовать метод log() для записи событий
    и verify_integrity() для проверки криптографической цепочки.
    """

    @abstractmethod
    def log(
            self,
            action: str,
            actor: str,
            *,
            target: str | None = None,
            status: str = "success",
            details: dict[str, object] | None = None,
    ) -> str:
        """Записывает событие в журнал аудита.

        Args:
            action: Название операции.
            actor: Субъект действия.
            target: Объект операции (опционально).
            status: Результат — 'success' или 'failed'.
            details: Произвольные детали события.

        Returns:
            Идентификатор (UUID) созданной записи.
        """

    @abstractmethod
    def verify_integrity(self) -> bool:
        """Проверяет целостность криптографической цепочки хэшей.

        Returns:
            True если цепочка не нарушена.

        Raises:
            AuditIntegrityError: Если обнаружено нарушение целостности.
        """
