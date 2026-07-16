import logging  # chutils: ignore[ChutilsIntegrationRule]

from .base import MetricsProvider
from .in_memory import InMemoryMetricsProvider
from .prometheus import PrometheusMetricsProvider, PROMETHEUS_AVAILABLE
from .timer import timer, TimerContext

__all__ = [
    "MetricsProvider",
    "InMemoryMetricsProvider",
    "PrometheusMetricsProvider",
    "PROMETHEUS_AVAILABLE",
    "get_provider",
    "set_provider",
    "increment",
    "set_gauge",
    "observe",
    "generate_latest",
    "clear",
    "timer",
    "TimerContext",
]

logger = logging.getLogger(__name__)

# Активный провайдер метрик
_active_provider: MetricsProvider | None = None


def get_provider() -> MetricsProvider:
    """Получить текущий активный провайдер метрик.
    
    Если провайдер не задан вручную, инициализирует PrometheusMetricsProvider
    (если библиотека доступна) или InMemoryMetricsProvider в качестве fallback.

    Returns:
        Текущий активный экземпляр MetricsProvider.
    """
    global _active_provider
    if _active_provider is None:
        # Пытаемся подгрузить плагины метрик
        try:
            from ..plugins import registry, MetricsPlugin
            registry.discover_plugins("chutils.plugins.metrics")
            external_metrics_providers = registry.get_plugins_by_type(MetricsPlugin)
            if external_metrics_providers:
                plugin = external_metrics_providers[0]
                _active_provider = plugin
                plugin_name = getattr(plugin, "name", "unknown")
                logger.debug(
                    f"Инициализирован внешний MetricsPlugin '{plugin_name}' в качестве основного провайдера метрик.")
        except Exception as e:
            logger.error(f"Ошибка при поиске плагинов метрик: {e}")

    if _active_provider is None:
        # Пытаемся получить настройки из chutils config
        # Чтобы не создавать циклическую зависимость при импорте get_config_value,
        # делаем импорт локально
        try:
            from chutils import get_config_value
            prefer_prometheus = get_config_value("Metrics", "prometheus_enabled", True)
        except Exception:
            prefer_prometheus = True

        if prefer_prometheus and PROMETHEUS_AVAILABLE:
            try:
                _active_provider = PrometheusMetricsProvider()
                logger.debug("Инициализирован PrometheusMetricsProvider в качестве основного провайдера метрик.")
            except Exception as e:
                logger.warning(
                    f"Не удалось инициализировать PrometheusMetricsProvider: {e}. Переключение на In-Memory.")
                _active_provider = InMemoryMetricsProvider()
        else:
            _active_provider = InMemoryMetricsProvider()
            logger.debug("Инициализирован InMemoryMetricsProvider в качестве основного провайдера метрик.")

    return _active_provider


def set_provider(provider: MetricsProvider) -> None:
    """Установить провайдер метрик вручную (например, для тестирования).

    Args:
        provider: Экземпляр MetricsProvider для установки.
    """
    global _active_provider
    _active_provider = provider


def increment(name: str, value: float = 1.0, labels: dict[str, str] | None = None) -> None:
    """Увеличить счетчик (Counter) на заданное значение.

    Args:
        name: Имя метрики.
        value: Значение, на которое нужно увеличить счетчик.
        labels: Словарь меток для метрики.
    """
    try:
        get_provider().increment(name, value, labels)
    except Exception as e:
        logger.error(f"Ошибка при вызове increment() для метрики '{name}': {e}")


def set_gauge(name: str, value: float, labels: dict[str, str] | None = None) -> None:
    """Установить значение датчика (Gauge).

    Args:
        name: Имя датчика.
        value: Устанавливаемое значение датчика.
        labels: Словарь меток для метрики.
    """
    try:
        get_provider().set_gauge(name, value, labels)
    except Exception as e:
        logger.error(f"Ошибка при вызове set_gauge() для метрики '{name}': {e}")


def observe(name: str, value: float, labels: dict[str, str] | None = None) -> None:
    """Записать значение в гистограмму/таймер (Histogram/Timer).

    Args:
        name: Имя метрики гистограммы/таймера.
        value: Наблюдаемое значение.
        labels: Словарь меток для метрики.
    """
    try:
        get_provider().observe(name, value, labels)
    except Exception as e:
        logger.error(f"Ошибка при вызове observe() для метрики '{name}': {e}")


def generate_latest() -> str:
    """Сгенерировать дамп последних метрик в текстовом формате.

    Returns:
        Дамп метрик в формате Prometheus или пустая строка при ошибке.
    """
    try:
        return get_provider().generate_latest()
    except Exception as e:
        logger.error(f"Ошибка при генерации отчета метрик: {e}")
        return ""


def clear() -> None:
    """
    Очистить данные активного провайдера метрик.
    """
    try:
        get_provider().clear()
    except Exception as e:
        logger.error(f"Ошибка при очистке метрик: {e}")
