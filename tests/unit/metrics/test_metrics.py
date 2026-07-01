import asyncio
import sys
import time
from unittest.mock import MagicMock, patch

import pytest

# Создаем мок для prometheus_client до импортов, чтобы тесты проходили независимо от окружения
try:
    import prometheus_client
except ImportError:
    mock_prom = MagicMock()
    mock_prom.generate_latest.return_value = b"test_prometheus_counter 1.0\ntest_prometheus_gauge 99.0\ntest_prometheus_histogram 0.123"
    sys.modules["prometheus_client"] = mock_prom

import chutils.metrics as metrics
from chutils.metrics.in_memory import InMemoryMetricsProvider
from chutils.metrics.prometheus import PrometheusMetricsProvider
from chutils.exceptions import OptionalDependencyError


@pytest.fixture(autouse=True)
def reset_provider():
    """Сбрасываем глобальный провайдер метрик перед каждым тестом."""
    metrics.clear()
    metrics.set_provider(None)
    yield
    metrics.clear()
    metrics.set_provider(None)


def test_in_memory_metrics_provider_basic():
    """Тест базовых операций InMemoryMetricsProvider."""
    provider = InMemoryMetricsProvider()
    
    # 1. Тест Counter
    provider.increment("http_requests_total", 2.0, {"method": "GET", "status": "200"})
    provider.increment("http_requests_total", 1.0, {"method": "GET", "status": "200"})
    provider.increment("http_requests_total", 1.0, {"method": "POST", "status": "201"})
    
    raw = provider.get_metrics()
    # Ищем записи в списке словарей
    get_rec = next(r for r in raw["counters"]["http_requests_total"] if r["labels"] == {"method": "GET", "status": "200"})
    assert get_rec["value"] == 3.0
    post_rec = next(r for r in raw["counters"]["http_requests_total"] if r["labels"] == {"method": "POST", "status": "201"})
    assert post_rec["value"] == 1.0

    # Проверим Prometheus дамп
    dump = provider.generate_latest()
    assert 'http_requests_total{method="GET",status="200"} 3.0' in dump
    assert 'http_requests_total{method="POST",status="201"} 1.0' in dump

    # 2. Тест Gauge
    provider.set_gauge("active_connections", 42.0)
    provider.set_gauge("active_connections", 10.0, {"host": "node1"})
    
    dump = provider.generate_latest()
    assert 'active_connections 42.0' in dump
    assert 'active_connections{host="node1"} 10.0' in dump

    # 3. Тест Histogram
    provider.observe("request_duration_seconds", 0.05, {"handler": "users"})
    provider.observe("request_duration_seconds", 0.5, {"handler": "users"})
    
    dump = provider.generate_latest()
    assert 'request_duration_seconds_sum{handler="users"} 0.55' in dump
    assert 'request_duration_seconds_count{handler="users"} 2' in dump
    assert 'request_duration_seconds_bucket{handler="users",le="0.1"} 1' in dump
    assert 'request_duration_seconds_bucket{handler="users",le="0.5"} 2' in dump


def test_in_memory_metrics_provider_clear():
    """Проверяет очистку данных в InMemoryMetricsProvider."""
    provider = InMemoryMetricsProvider()
    provider.increment("c1")
    assert "c1" in provider.generate_latest()
    provider.clear()
    assert provider.generate_latest() == ""


def test_prometheus_metrics_provider_basic():
    """Тест базовых операций PrometheusMetricsProvider (при наличии библиотеки)."""
    # Патчим PROMETHEUS_AVAILABLE, чтобы позволить инстанцировать класс даже без реальной библиотеки
    with patch("chutils.metrics.prometheus.PROMETHEUS_AVAILABLE", True):
        provider = PrometheusMetricsProvider()
        
        # Имитируем вызовы
        provider.increment("test_prometheus_counter", 1.0, {"app": "test"})
        provider.set_gauge("test_prometheus_gauge", 99.0, {"app": "test"})
        provider.observe("test_prometheus_histogram", 0.123, {"app": "test"})

        dump = provider.generate_latest()
        assert "test_prometheus_counter" in dump
        assert "test_prometheus_gauge" in dump
        assert "test_prometheus_histogram" in dump


def test_timer_context_and_decorator_sync():
    """Проверяет работу таймера в качестве контекстного менеджера и декоратора (синхронно)."""
    provider = InMemoryMetricsProvider()
    metrics.set_provider(provider)

    # 1. Контекстный менеджер
    with metrics.timer("block_duration", {"step": "1"}):
        time.sleep(0.01)

    raw = provider.get_metrics()
    assert len(raw["histograms"]["block_duration"]) == 1
    assert raw["histograms"]["block_duration"][0]["labels"] == {"step": "1"}
    assert raw["histograms"]["block_duration"][0]["values"][0] >= 0.01

    # 2. Декоратор
    @metrics.timer("func_duration", {"func": "test"})
    def my_func():
        time.sleep(0.01)

    my_func()
    raw = provider.get_metrics()
    assert len(raw["histograms"]["func_duration"]) == 1
    assert raw["histograms"]["func_duration"][0]["labels"] == {"func": "test"}


@pytest.mark.asyncio
async def test_timer_decorator_async():
    """Проверяет работу таймера в качестве декоратора для асинхронных функций."""
    provider = InMemoryMetricsProvider()
    metrics.set_provider(provider)

    @metrics.timer("async_func_duration", {"func": "async_test"})
    async def my_async_func():
        await asyncio.sleep(0.01)

    await my_async_func()
    raw = provider.get_metrics()
    assert len(raw["histograms"]["async_func_duration"]) == 1
    assert raw["histograms"]["async_func_duration"][0]["labels"] == {"func": "async_test"}
    assert raw["histograms"]["async_func_duration"][0]["values"][0] >= 0.01


def test_facade_auto_switch():
    """Тест автоматического переключения провайдера на основе доступности зависимости."""
    # Тест случая, когда prometheus_client доступен
    with patch("chutils.metrics.PROMETHEUS_AVAILABLE", True), \
         patch("chutils.metrics.prometheus.PROMETHEUS_AVAILABLE", True):
        # Очищаем кэш провайдера, чтобы форсировать создание нового
        metrics._active_provider = None
        provider = metrics.get_provider()
        assert isinstance(provider, PrometheusMetricsProvider)


def test_metrics_no_dependency_fallback():
    """
    КРИТИЧЕСКИЙ ТЕСТ:
    Проверяет, что при отсутствии библиотеки prometheus_client:
    1. Глобальный фасад автоматически переключается на InMemoryMetricsProvider и не падает.
    2. Все вызовы функций (increment, set_gauge, observe) продолжают корректно работать.
    3. Создание PrometheusMetricsProvider вручную выбрасывает понятную OptionalDependencyError.
    """
    with patch("chutils.metrics.prometheus.PROMETHEUS_AVAILABLE", False), \
         patch("chutils.metrics.PROMETHEUS_AVAILABLE", False):
        
        # Сбрасываем провайдер
        metrics._active_provider = None
        
        # 1. Проверяем авто-переключение на InMemoryMetricsProvider
        provider = metrics.get_provider()
        assert isinstance(provider, InMemoryMetricsProvider)
        
        # 2. Вызываем методы фасада. Они должны успешно отрабатывать через In-Memory сборщик
        metrics.increment("test_fallback_counter", 5.0, {"env": "prod"})
        metrics.set_gauge("test_fallback_gauge", 2.0)
        metrics.observe("test_fallback_histogram", 0.01)
        
        dump = metrics.generate_latest()
        assert 'test_fallback_counter{env="prod"} 5.0' in dump
        assert 'test_fallback_gauge 2.0' in dump
        assert 'test_fallback_histogram_count 1' in dump

        # 3. Проверяем, что ручное создание PrometheusMetricsProvider выбрасывает OptionalDependencyError
        with pytest.raises(OptionalDependencyError) as exc_info:
            PrometheusMetricsProvider()
        
        assert "prometheus_client" in str(exc_info.value)
        assert exc_info.value.context["dependency"] == "prometheus_client"
        assert exc_info.value.hint is not None
