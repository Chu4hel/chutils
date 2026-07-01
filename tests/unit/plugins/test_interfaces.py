from __future__ import annotations

import logging

import pytest

from chutils.plugins import (
    BasePlugin,
    ConfigProviderPlugin,
    LoggerHandlerPlugin,
    MetricsPlugin,
    SecretProviderPlugin,
)


def test_base_plugin_is_abstract():
    """Проверяет, что BasePlugin нельзя инстанцировать напрямую."""
    with pytest.raises(TypeError):
        BasePlugin()  # type: ignore


def test_secret_provider_plugin_interface():
    """Проверяет корректность реализации SecretProviderPlugin."""

    class MySecretPlugin(SecretProviderPlugin):
        @property
        def name(self) -> str:
            return "my-secret-plugin"

        def get(self, key: str, service_name: str) -> str | None:
            return "secret-value"

        def set(self, key: str, value: str, service_name: str) -> bool:
            return True

        def delete(self, key: str, service_name: str) -> bool:
            return True

    plugin = MySecretPlugin()
    assert plugin.name == "my-secret-plugin"
    assert plugin.version == "0.1.0"
    assert plugin.get("key", "srv") == "secret-value"
    assert plugin.set("key", "val", "srv") is True
    assert plugin.delete("key", "srv") is True


def test_config_provider_plugin_interface():
    """Проверяет корректность реализации ConfigProviderPlugin."""

    class MyConfigPlugin(ConfigProviderPlugin):
        @property
        def name(self) -> str:
            return "my-config-plugin"

        def load(self, path: str) -> dict[str, Any]:
            return {"key": "value"}

        def save(self, path: str, section: str, key: str, value: Any) -> bool:
            return True

    plugin = MyConfigPlugin()
    assert plugin.name == "my-config-plugin"
    assert plugin.load("path") == {"key": "value"}
    assert plugin.save("path", "sec", "key", "val") is True


def test_logger_handler_plugin_interface():
    """Проверяет корректность реализации LoggerHandlerPlugin."""

    class MyLoggerPlugin(LoggerHandlerPlugin):
        @property
        def name(self) -> str:
            return "my-logger-plugin"

        def get_handler(self, **kwargs: Any) -> logging.Handler:
            return logging.NullHandler()

    plugin = MyLoggerPlugin()
    assert plugin.name == "my-logger-plugin"
    assert isinstance(plugin.get_handler(), logging.NullHandler)


def test_metrics_plugin_interface():
    """Проверяет корректность реализации MetricsPlugin."""

    class MyMetricsPlugin(MetricsPlugin):
        @property
        def name(self) -> str:
            return "my-metrics-plugin"

        def increment(self, name: str, value: float = 1.0, labels: dict[str, str] | None = None) -> None:
            pass

        def set_gauge(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
            pass

        def observe(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
            pass

        def generate_latest(self) -> str:
            return "metrics-data"

        def clear(self) -> None:
            pass

    plugin = MyMetricsPlugin()
    assert plugin.name == "my-metrics-plugin"
    assert plugin.generate_latest() == "metrics-data"
