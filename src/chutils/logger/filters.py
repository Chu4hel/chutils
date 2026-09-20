"""
Фильтры для логирования.

Содержит специализированные фильтры logging.Filter, включая FlappingFilter для
подавления ложных транзиентных сбоев (флаппинга) и защиты от спама алертов.
"""

from __future__ import annotations

import logging  # chutils: ignore[ChutilsIntegrationRule]
import re
import threading
import time
from collections.abc import Callable, Sequence

__all__ = ["FlappingFilter"]


class FlappingFilter(logging.Filter):
    """
    Интеллектуальный фильтр для подавления кратковременных транзиентных ошибок (флаппинга).

    При возникновении ошибок, соответствующих заданным шаблонам, фильтр отслеживает
    количество непрерывных сбоев и их длительность. До достижения заданного порога
    (по количеству попыток или времени) ошибки либо понижаются в уровне (например,
    до INFO, чтобы не триггерить ERROR-алерты в Telegram, но оставаться в файловом логе),
    либо полностью отсекаются.

    Если порог превышен (сервис действительно недоступен), фильтр пропускает ошибку
    как полноценный ERROR (или исходный уровень) и опционально обогащает сообщение
    данными о длительности сбоя и количестве неудачных попыток.
    """

    def __init__(
        self,
        patterns: str | re.Pattern[str] | Sequence[str | re.Pattern[str]],
        threshold: int = 3,
        failure_timeout: float = 60.0,
        action: str = "downgrade",
        downgrade_level: int = logging.INFO,
        enrich_message: bool = True,
        auto_reset_on_success: bool = True,
        on_escalated: Callable[[logging.LogRecord, int, float], None] | None = None,
        on_recovered: Callable[[float], None] | None = None,
    ) -> None:
        """
        Инициализирует фильтр флаппинга.

        Args:
            patterns: Строка, регулярное выражение или последовательность строк/регулярок,
                совпадение с которыми классифицирует сообщение как флаппинг-ошибку.
            threshold: Количество непрерывных сбоев до эскалации (по умолчанию 3).
            failure_timeout: Максимальное время в секундах от первого сбоя до эскалации
                (по умолчанию 60.0).
            action: Действие до достижения порога: 'downgrade' (понизить уровень)
                или 'drop' (полностью отбросить запись).
            downgrade_level: Числовой уровень логирования для действия 'downgrade'
                (по умолчанию logging.INFO).
            enrich_message: Добавлять ли в сообщение префикс с диагностикой сбоя
                при превышении порога.
            auto_reset_on_success: Автоматически сбрасывать счётчик сбоев при получении
                любой другой записи лога с уровнем ниже ERROR.
            on_escalated: Опциональный callback(record, consecutive_failures, duration),
                вызываемый при первом превышении порога.
            on_recovered: Опциональный callback(downtime_duration), вызываемый
                при успешном восстановлении после подтвержденной аварии.
        """
        super().__init__()

        if isinstance(patterns, (str, re.Pattern)):
            self._patterns: list[str | re.Pattern[str]] = [patterns]
        else:
            self._patterns = list(patterns)

        self.threshold = max(1, threshold)
        self.failure_timeout = max(0.0, failure_timeout)
        self.action = action.lower()
        self.downgrade_level = downgrade_level
        self.enrich_message = enrich_message
        self.auto_reset_on_success = auto_reset_on_success
        self.on_escalated = on_escalated
        self.on_recovered = on_recovered

        self._consecutive_failures = 0
        self._first_failure_time: float | None = None
        self._has_escalated = False
        self._lock = threading.Lock()

    @property
    def consecutive_failures(self) -> int:
        """Текущее количество последовательных сбоев."""
        with self._lock:
            return self._consecutive_failures

    @property
    def is_escalated(self) -> bool:
        """Флаг того, что сбой в данный момент превысил порог и эскалирован."""
        with self._lock:
            return self._has_escalated

    def _matches(self, message: str) -> bool:
        """Проверяет, совпадает ли сообщение с одним из шаблонов."""
        for pat in self._patterns:
            if isinstance(pat, str):
                if pat in message:
                    return True
            elif pat.search(message):
                return True
        return False

    def reset(self) -> None:
        """
        Сбрасывает состояние счетчиков и таймеров сбоев.
        """
        with self._lock:
            self._do_reset()

    def _do_reset(self) -> None:
        """Внутренний сброс без захвата блокировки."""
        if (
            self._has_escalated
            and self.on_recovered
            and self._first_failure_time is not None
        ):
            duration = time.monotonic() - self._first_failure_time
            try:
                self.on_recovered(duration)
            except Exception:
                pass

        self._consecutive_failures = 0
        self._first_failure_time = None
        self._has_escalated = False

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Фильтрует или модифицирует запись лога.

        Args:
            record: Объект LogRecord стандартной библиотеки logging.

        Returns:
            True, если запись должна быть сохранена/передана дальше, False для отсечения.
        """
        message = record.getMessage()

        with self._lock:
            is_matching_error = self._matches(message)

            if not is_matching_error:
                # Если это не флаппинг-ошибка и включен автосброс
                if (
                    self.auto_reset_on_success
                    and record.levelno < logging.ERROR
                    and self._consecutive_failures > 0
                ):
                    self._do_reset()
                return True

            now = time.monotonic()
            self._consecutive_failures += 1

            if self._first_failure_time is None:
                self._first_failure_time = now

            duration = now - self._first_failure_time

            # Проверяем, превышен ли порог
            is_exceeded = (
                self._consecutive_failures >= self.threshold
                or duration >= self.failure_timeout
            )

            if not is_exceeded:
                # Порог ещё не достигнут (транзиентный сбой)
                if self.action == "drop":
                    return False

                # Действие downgrade: понижаем уровень лога
                record.levelno = self.downgrade_level
                record.levelname = logging.getLevelName(self.downgrade_level)
                return True

            # Порог превышен: настоящая авария / длительный отказ
            if not self._has_escalated:
                self._has_escalated = True
                if self.on_escalated:
                    try:
                        self.on_escalated(record, self._consecutive_failures, duration)
                    except Exception:
                        pass

            if self.enrich_message:
                prefix = (
                    f"[DOWNTIME THRESHOLD EXCEEDED "
                    f"(сбоев: {self._consecutive_failures}, длительность: {duration:.1f}с)] "
                )
                if isinstance(record.msg, str) and not record.msg.startswith(
                    "[DOWNTIME THRESHOLD EXCEEDED"
                ):
                    record.msg = f"{prefix}{record.msg}"

            return True

            return True
