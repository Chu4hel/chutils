import importlib.util
import threading
from typing import Any

from chutils.exceptions import OptionalDependencyError
from .base import MetricsProvider

PROMETHEUS_AVAILABLE = importlib.util.find_spec("prometheus_client") is not None
"Глобальный флаг доступности prometheus_client"


class PrometheusMetricsProvider(MetricsProvider):
    """
    Провайдер метрик, транслирующий вызовы в prometheus_client.
    
    Использует ленивый импорт. Если библиотека prometheus_client отсутствует,
    выбрасывает OptionalDependencyError при инициализации.
    """

    def __init__(self) -> None:
        """Инициализирует PrometheusMetricsProvider."""
        if not PROMETHEUS_AVAILABLE:
            raise OptionalDependencyError(
                "Библиотека 'prometheus_client' не установлена.",
                dependency="prometheus_client",
                hint="Установите ее с помощью 'pip install chutils[metrics]' или 'pip install prometheus-client'."
            )

        self._lock = threading.Lock()
        # Кэш созданных объектов метрик: { (name, label_names): prometheus_metric_object }
        self._metrics: dict[tuple[str, tuple[str, ...]], Any] = {}

    def _get_or_create_metric(self, name: str, metric_type: str, labels: dict[str, str] | None) -> Any:
        label_names = sorted(labels.keys()) if labels else []
        cache_key = (name, tuple(label_names))

        with self._lock:
            if cache_key in self._metrics:
                return self._metrics[cache_key]

            # Создаем метрику в зависимости от типа
            import prometheus_client

            if metric_type == "counter":
                metric: Any = prometheus_client.Counter(name, f"Counter for {name}", labelnames=label_names)
            elif metric_type == "gauge":
                metric = prometheus_client.Gauge(name, f"Gauge for {name}", labelnames=label_names)
            elif metric_type == "histogram":
                # Используем дефолтные бакеты prometheus_client
                metric = prometheus_client.Histogram(name, f"Histogram for {name}", labelnames=label_names)
            else:
                raise ValueError(f"Неизвестный тип метрики: {metric_type}")

            self._metrics[cache_key] = metric
            return metric

    def increment(self, name: str, value: float = 1.0, labels: dict[str, str] | None = None) -> None:
        """Увеличить счетчик (Counter) на заданное значение.

        Args:
            name: Имя метрики.
            value: Добавляемое значение.
            labels: Словарь меток.
        """
        metric = self._get_or_create_metric(name, "counter", labels)
        if labels:
            metric.labels(**labels).inc(value)
        else:
            metric.inc(value)

    def set_gauge(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        """Установить значение датчика (Gauge).

        Args:
            name: Имя датчика.
            value: Устанавливаемое значение.
            labels: Словарь меток.
        """
        metric = self._get_or_create_metric(name, "gauge", labels)
        if labels:
            metric.labels(**labels).set(value)
        else:
            metric.set(value)

    def observe(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        """Записать значение в гистограмму/таймер (Histogram/Timer).

        Args:
            name: Имя метрики.
            value: Записываемое значение.
            labels: Словарь меток.
        """
        metric = self._get_or_create_metric(name, "histogram", labels)
        if labels:
            metric.labels(**labels).observe(value)
        else:
            metric.observe(value)

    def generate_latest(self) -> str:
        """Экспортировать накопленные метрики в текстовом формате.

        Returns:
            Строка с отформатированными метриками.
        """
        import prometheus_client
        return prometheus_client.generate_latest().decode("utf-8")

    def clear(self) -> None:
        """Очистить кэш провайдера (но не глобальный REGISTRY Prometheus)."""
        with self._lock:
            self._metrics.clear()
