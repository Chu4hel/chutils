from abc import ABC, abstractmethod


class MetricsProvider(ABC):
    """
    Абстрактный базовый класс (интерфейс) для провайдеров метрик.
    """

    @abstractmethod
    def increment(self, name: str, value: float = 1.0, labels: dict[str, str] | None = None) -> None:
        """Увеличить счетчик (Counter) на заданное значение.

        Args:
            name: Имя метрики.
            value: Значение, на которое нужно увеличить счетчик.
            labels: Словарь меток для метрики.
        """
        pass

    @abstractmethod
    def set_gauge(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        """Установить значение датчика (Gauge).

        Args:
            name: Имя датчика.
            value: Устанавливаемое значение датчика.
            labels: Словарь меток для метрики.
        """
        pass

    @abstractmethod
    def observe(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        """Записать значение в гистограмму/таймер (Histogram/Timer).

        Args:
            name: Имя метрики гистограммы/таймера.
            value: Наблюдаемое значение.
            labels: Словарь меток для метрики.
        """
        pass

    @abstractmethod
    def generate_latest(self) -> str:
        """Экспортировать накопленные метрики в текстовом формате.

        Returns:
            Строка с накопленными метриками.
        """
        pass

    @abstractmethod
    def clear(self) -> None:
        """
        Очистить все накопленные данные (для тестов).
        """
        pass
