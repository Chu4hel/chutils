"""
Модели данных для модуля chutils.scraping.concurrency.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ScrapingTask:
    """Модель задачи скрапинга.

    Attributes:
        url: Целевой URL.
        priority: Числовой приоритет (чем выше, тем раньше выполняется).
        payload: Произвольный словарь пользовательских данных.
        attempts: Количество предпринятых попыток выполнения.
        max_attempts: Максимально допустимое количество попыток.
        task_id: Уникальный идентификатор задачи.
        dedup_key: Ключ для дедупликации (по умолчанию совпадает с url).
        created_at: Временная метка создания задачи.
        last_error: Сообщение о последней возникшей ошибке.
    """

    url: str
    priority: int = 0
    payload: dict[str, Any] = field(default_factory=dict)
    attempts: int = 0
    max_attempts: int = 3
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    dedup_key: str = ""
    created_at: float = field(default_factory=time.time)
    last_error: str | None = None

    def __post_init__(self) -> None:
        if not self.dedup_key:
            self.dedup_key = self.url
