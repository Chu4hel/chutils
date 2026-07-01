from __future__ import annotations

import logging
import sys
from unittest.mock import MagicMock, patch

import pytest

import chutils.config.core
from chutils.config import get_config
from chutils.config.manager import _cm
from chutils.config.providers import get_providers
from chutils.config.utils import _nest_ini_dict
from chutils.logger import setup_logger
from chutils.metrics import get_provider, set_provider
from chutils.plugins import (
    ConfigProviderPlugin,
    LoggerHandlerPlugin,
    MetricsPlugin,
    SecretProviderPlugin,
    registry,
)
from chutils.secret_manager import SecretManager


class DummyHandler(logging.Handler):
    """Простой обработчик для тестов, чтобы не использовать строгий Mock."""
    pass


@pytest.fixture(autouse=True)
def cleanup_registry():
    registry.clear()
    _cm.clear_cache()

    # Полный сброс состояния плагинов конфигурации перед тестом
    chutils.config.core._config_plugins_loaded = False
    chutils.config.core._PROVIDERS = get_providers(_nest_ini_dict)

    yield

    registry.clear()
    _cm.clear_cache()

    # Полный сброс состояния плагинов конфигурации после теста
    chutils.config.core._config_plugins_loaded = False
    chutils.config.core._PROVIDERS = get_providers(_nest_ini_dict)
    set_provider(None)  # Сброс провайдера метрик


def make_mock_entry_points(target_group: str, mock_ep: MagicMock):
    """Вспомогательная функция для создания мока entry_points с фильтрацией по группе."""

    def side_effect(*args, **kwargs):
        group = kwargs.get("group")
        if not group and args:
            group = args[0]

        if sys.version_info >= (3, 10):
            if group == target_group:
                return [mock_ep]
            return []
        else:
            mock_eps_dict = MagicMock()
            if group == target_group:
                mock_eps_dict.get.return_value = [mock_ep]
                mock_eps_dict.select.return_value = [mock_ep]
            else:
                mock_eps_dict.get.return_value = []
                mock_eps_dict.select.return_value = []
            return mock_eps_dict

    return side_effect


@patch("importlib.metadata.entry_points")
def test_lazy_loading_secret_manager(mock_entry_points):
    """Проверяет, что плагины SecretProviderPlugin загружаются лениво."""
    mock_ep = MagicMock()
    mock_ep.name = "mock_secret"
    mock_ep.value = "mock_secret_module:MockSecret"

    class MockSecretPlugin(SecretProviderPlugin):
        name = "lazy_secret"

        def get(self, key: str, service_name: str) -> str | None:
            return "secret-data"

        def set(self, key: str, value: str, service_name: str) -> bool:
            return True

        def delete(self, key: str, service_name: str) -> bool:
            return True

    mock_ep.load.return_value = MockSecretPlugin
    mock_entry_points.side_effect = make_mock_entry_points("chutils.plugins.secret", mock_ep)

    # 1. Создание SecretManager не должно приводить к загрузке плагина
    sm = SecretManager(service_name="test_lazy")
    assert not mock_ep.load.called

    # 2. Обращение к секрету должно привести к ленивой загрузке плагина
    val = sm.get_secret("any_key")
    assert mock_ep.load.called
    assert val == "secret-data"


@patch("importlib.metadata.entry_points")
def test_lazy_loading_config_manager(mock_entry_points, tmp_path):
    """Проверяет, что плагины ConfigProviderPlugin загружаются лениво."""
    mock_ep = MagicMock()
    mock_ep.name = "mock_config"
    mock_ep.value = "mock_config_module:MockConfig"

    class MockConfigPlugin(ConfigProviderPlugin):
        name = "toml"
        supported_extensions = [".toml"]

        def load(self, path: str) -> dict[str, Any]:
            return {"toml_key": "toml_value"}

        def save(self, path: str, section: str, key: str, value: Any) -> bool:
            return True

    mock_ep.load.return_value = MockConfigPlugin
    mock_entry_points.side_effect = make_mock_entry_points("chutils.plugins.config", mock_ep)

    # 1. До вызова get_config с файлом .toml плагин не должен загружаться
    toml_file = tmp_path / "config.toml"
    toml_file.write_text("dummy")

    assert not mock_ep.load.called

    # 2. Загрузка конфигурации из файла с расширением .toml должна триггерить плагин
    old_paths = (_cm._config_file_path, _cm._paths_initialized)
    _cm._config_file_path = str(toml_file)
    _cm._paths_initialized = True

    try:
        data = get_config()
        assert mock_ep.load.called
        assert data.get("toml_key") == "toml_value"
    finally:
        _cm._config_file_path, _cm._paths_initialized = old_paths


@patch("importlib.metadata.entry_points")
def test_lazy_loading_logger_handler(mock_entry_points):
    """Проверяет, что плагины LoggerHandlerPlugin загружаются лениво."""
    mock_ep = MagicMock()
    mock_ep.name = "mock_logger"
    mock_ep.value = "mock_logger_module:MockLogger"

    mock_handler = DummyHandler()

    class MockLoggerPlugin(LoggerHandlerPlugin):
        name = "lazy_logger"

        def get_handler(self, **kwargs: Any) -> logging.Handler:
            return mock_handler

    mock_ep.load.return_value = MockLoggerPlugin
    mock_entry_points.side_effect = make_mock_entry_points("chutils.plugins.logger", mock_ep)

    # 1. До вызова setup_logger плагин не должен загружаться
    assert not mock_ep.load.called

    # 2. setup_logger должен лениво загрузить плагин и добавить его хэндлер
    logger_instance = setup_logger("test_lazy_logger", force_reconfigure=True)
    assert mock_ep.load.called
    assert mock_handler in logger_instance.handlers


@patch("importlib.metadata.entry_points")
def test_lazy_loading_metrics(mock_entry_points):
    """Проверяет, что плагины MetricsPlugin загружаются лениво."""
    mock_ep = MagicMock()
    mock_ep.name = "mock_metrics"
    mock_ep.value = "mock_metrics_module:MockMetrics"

    class MockMetricsPlugin(MetricsPlugin):
        name = "lazy_metrics"

        def increment(self, name: str, value: float = 1.0, labels: dict[str, str] | None = None) -> None:
            pass

        def set_gauge(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
            pass

        def observe(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
            pass

        def generate_latest(self) -> str:
            return "lazy-data"

        def clear(self) -> None:
            pass

    mock_ep.load.return_value = MockMetricsPlugin
    mock_entry_points.side_effect = make_mock_entry_points("chutils.plugins.metrics", mock_ep)

    # 1. До первого получения провайдера плагин не должен загружаться
    assert not mock_ep.load.called

    # 2. Получение провайдера должно запустить ленивую загрузку
    provider = get_provider()
    assert mock_ep.load.called
    assert provider.generate_latest() == "lazy-data"
