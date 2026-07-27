"""
Базовый абстрактный класс очереди задач скрапинга.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import ScrapingTask


class BaseTaskQueue(ABC):
    """Абстрактная очередь задач скрапинга."""

    @abstractmethod
    async def push(self, task: ScrapingTask) -> bool:
        """Добавляет задачу в очередь.

        Args:
            task: Задача для добавления.

        Returns:
            True, если задача добавлена; False, если задача дедуплицирована.
        """

    @abstractmethod
    async def pop(self) -> ScrapingTask | None:
        """Извлекает задачу с наибольшим приоритетом из очереди.

        Returns:
            Экземпляр ScrapingTask или None, если очередь пуста.
        """

    @abstractmethod
    async def complete(self, task: ScrapingTask) -> None:
        """Помечает задачу как успешно выполненную.

        Args:
            task: Выполненная задача.
        """

    @abstractmethod
    async def fail(self, task: ScrapingTask, error: str) -> None:
        """Обрабатывает ошибку выполнения задачи.

        Args:
            task: Сбойная задача.
            error: Текст ошибки.
        """

    @abstractmethod
    async def size(self) -> int:
        """Возвращает количество элементов в очереди.

        Returns:
            Размер очереди.
        """

    @abstractmethod
    async def clear(self) -> None:
        """Очищает очередь и сбрасывает историю дедупликации."""
