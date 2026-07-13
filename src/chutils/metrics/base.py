from abc import ABC, abstractmethod


class MetricsProvider(ABC):
    """
    Абстрактный базовый класс (интерфейс) для провайдеров метрик.
    """

    @abstractmethod
    def increment(self, name: str, value: float = 1.0, labels: dict[str, str] | None = None) -> None:
        """
        Увеличить счетчик (Counter) на заданное значение.
        """
        pass

    @abstractmethod
    def set_gauge(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        """
        Установить значение датчика (Gauge).
        """
        pass

    @abstractmethod
    def observe(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        """
        Записать значение в гистограмму/таймер (Histogram/Timer).
        """
        pass

    @abstractmethod
    def generate_latest(self) -> str:
        """
        Экспортировать накопленные метрики в текстовом формате.
        """
        pass

    @abstractmethod
    def clear(self) -> None:
        """
        Очистить все накопленные данные (для тестов).
        """
        pass
