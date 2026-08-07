"""Модуль сбора Prometheus-метрических показателей для очередей задач и воркеров."""

from chutils import metrics


class QueueMetricsCollector:
    """Коллектор метрик для очередей и воркеров."""

    def __init__(self, queue_name: str, queue_type: str, enabled: bool = True) -> None:
        self.queue_name = queue_name
        self.queue_type = queue_type
        self.enabled = enabled

    def set_pending_size(self, size: int) -> None:
        """Установить текущий размер очереди.

        Args:
            size: Размер очереди.
        """
        if self.enabled:
            metrics.set_gauge(
                "chutils_queue_pending_size",
                float(size),
                labels={"queue_name": self.queue_name, "queue_type": self.queue_type},
            )

    def inc_tasks_processed(self, status: str = "completed") -> None:
        """Увеличить счетчик обработанных задач.

        Args:
            status: Статус обработки (completed, failed, retried).
        """
        if self.enabled:
            metrics.increment(
                "chutils_tasks_processed_total",
                1.0,
                labels={"queue_name": self.queue_name, "status": status},
            )

    def observe_execution_duration(self, duration_seconds: float, status: str = "completed") -> None:
        """Записать время выполнения задачи.

        Args:
            duration_seconds: Длительность выполнения в секундах.
            status: Статус выполнения задачи.
        """
        if self.enabled:
            metrics.observe(
                "chutils_task_execution_duration_seconds",
                duration_seconds,
                labels={"queue_name": self.queue_name, "status": status},
            )

    def set_active_workers(self, active_count: int) -> None:
        """Установить число активных воркеров.

        Args:
            active_count: Количество активных воркеров.
        """
        if self.enabled:
            metrics.set_gauge(
                "chutils_worker_pool_active_workers",
                float(active_count),
                labels={"queue_name": self.queue_name},
            )
