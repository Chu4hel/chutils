import threading
from typing import Any

from .base import MetricsProvider


class InMemoryMetricsProvider(MetricsProvider):
    """
    Потокобезопасный in-memory провайдер метрик.
    
    Не требует внешних зависимостей. Форматирует экспорт в стандартный
    текстовый формат Prometheus для бесшовной интеграции.
    """

    # Стандартные бакеты для Histogram (в секундах/величинах)
    DEFAULT_BUCKETS: list[float] = [
        0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0
    ]

    def __init__(self) -> None:
        """Инициализирует InMemoryMetricsProvider."""
        self._lock = threading.Lock()
        # Структура: {metric_name: {frozenset_labels: value}}
        self._counters: dict[str, dict[frozenset[tuple[str, str]], float]] = {}
        self._gauges: dict[str, dict[frozenset[tuple[str, str]], float]] = {}
        # Структура: {metric_name: {frozenset_labels: [values]}}
        self._histograms: dict[str, dict[frozenset[tuple[str, str]], list[float]]] = {}

    def _get_labels_key(self, labels: dict[str, str] | None) -> frozenset[tuple[str, str]]:
        if not labels:
            return frozenset()
        return frozenset(labels.items())

    def increment(self, name: str, value: float = 1.0, labels: dict[str, str] | None = None) -> None:
        """Увеличить счетчик (Counter) на заданное значение.

        Args:
            name: Имя метрики.
            value: Добавляемое значение.
            labels: Словарь меток.
        """
        key = self._get_labels_key(labels)
        with self._lock:
            if name not in self._counters:
                self._counters[name] = {}
            self._counters[name][key] = self._counters[name].get(key, 0.0) + value

    def set_gauge(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        """Установить значение датчика (Gauge).

        Args:
            name: Имя датчика.
            value: Устанавливаемое значение.
            labels: Словарь меток.
        """
        key = self._get_labels_key(labels)
        with self._lock:
            if name not in self._gauges:
                self._gauges[name] = {}
            self._gauges[name][key] = value

    def observe(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        """Записать значение в гистограмму/таймер (Histogram/Timer).

        Args:
            name: Имя метрики.
            value: Записываемое значение.
            labels: Словарь меток.
        """
        key = self._get_labels_key(labels)
        with self._lock:
            if name not in self._histograms:
                self._histograms[name] = {}
            if key not in self._histograms[name]:
                self._histograms[name][key] = []
            self._histograms[name][key].append(value)

    def generate_latest(self) -> str:
        """Экспортировать накопленные метрики в текстовом формате.

        Returns:
            Строка с отформатированными метриками.
        """
        lines: list[str] = []

        with self._lock:
            # 1. Форматируем Counters
            for name, labels_dict in self._counters.items():
                lines.append(f"# TYPE {name} counter")
                for labels_set, value in labels_dict.items():
                    lbl_str = self._format_labels(labels_set)
                    lines.append(f"{name}{lbl_str} {value}")

            # 2. Форматируем Gauges
            for name, labels_dict in self._gauges.items():
                lines.append(f"# TYPE {name} gauge")
                for labels_set, value in labels_dict.items():
                    lbl_str = self._format_labels(labels_set)
                    lines.append(f"{name}{lbl_str} {value}")

            # 3. Форматируем Histograms
            for name, hist_dict in self._histograms.items():
                lines.append(f"# TYPE {name} histogram")
                for labels_set, values in hist_dict.items():
                    # Считаем сумму и количество
                    count = len(values)
                    total_sum = sum(values)

                    # Считаем бакеты
                    buckets_counts = {b: 0 for b in self.DEFAULT_BUCKETS}
                    inf_count = 0
                    for val in values:
                        for b in self.DEFAULT_BUCKETS:
                            if val <= b:
                                buckets_counts[b] += 1
                        inf_count += 1

                    # Выводим бакеты в формате Prometheus
                    for b in self.DEFAULT_BUCKETS:
                        b_labels = dict(labels_set)
                        b_labels["le"] = str(b)
                        lbl_str = self._format_labels(frozenset(b_labels.items()))
                        lines.append(f"{name}_bucket{lbl_str} {buckets_counts[b]}")

                    # Выводим бакет +Inf
                    inf_labels = dict(labels_set)
                    inf_labels["le"] = "+Inf"
                    lbl_str = self._format_labels(frozenset(inf_labels.items()))
                    lines.append(f"{name}_bucket{lbl_str} {inf_count}")

                    # Выводим _sum и _count
                    lbl_str = self._format_labels(labels_set)
                    lines.append(f"{name}_sum{lbl_str} {total_sum}")
                    lines.append(f"{name}_count{lbl_str} {count}")

        return "\n".join(lines) + "\n" if lines else ""

    def _format_labels(self, labels_set: frozenset[tuple[str, str]]) -> str:
        if not labels_set:
            return ""
        items = [f'{k}="{v}"' for k, v in sorted(labels_set)]
        return "{" + ",".join(items) + "}"

    def get_metrics(self) -> dict[str, Any]:
        """Возвращает сырые накопленные метрики в виде словаря (для отладки и тестов).

        Returns:
            Словарь с сырыми данными по счетчикам, датчикам и гистограммам.
        """
        with self._lock:
            return {
                "counters": {
                    name: [{"labels": dict(labels_set), "value": value} for labels_set, value in labels_dict.items()]
                    for name, labels_dict in self._counters.items()
                },
                "gauges": {
                    name: [{"labels": dict(labels_set), "value": value} for labels_set, value in labels_dict.items()]
                    for name, labels_dict in self._gauges.items()
                },
                "histograms": {
                    name: [{"labels": dict(labels_set), "values": values} for labels_set, values in hist_dict.items()]
                    for name, hist_dict in self._histograms.items()
                }
            }

    def clear(self) -> None:
        """Очищает все накопленные данные метрик."""
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()
