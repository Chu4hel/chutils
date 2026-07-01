"""
Модуль системы плагинов для chutils.
Позволяет расширять провайдеры секретов, конфигураций, метрик и логирования.
"""
from .core import PluginError, PluginRegistry, register_plugin, registry
from .interfaces import (
    BasePlugin,
    ConfigProviderPlugin,
    LoggerHandlerPlugin,
    MetricsPlugin,
    SecretProviderPlugin,
)

__all__ = [
    "PluginRegistry",
    "registry",
    "register_plugin",
    "PluginError",
    "BasePlugin",
    "SecretProviderPlugin",
    "ConfigProviderPlugin",
    "LoggerHandlerPlugin",
    "MetricsPlugin",
]
