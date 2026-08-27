"""
Модуль системы плагинов для chutils.
Позволяет расширять провайдеры секретов, конфигураций, метрик и логирования.
"""
from .core import (
    PluginError,
    PluginRegistry,
    get_browser_stealth_plugins,
    get_captcha_solver_plugin,
    get_http_backend_plugin,
    get_task_queue_plugin,
    register_plugin,
    registry,
)
from .interfaces import (
    BasePlugin,
    BrowserStealthPlugin,
    CaptchaSolverPlugin,
    ConfigProviderPlugin,
    HttpBackendPlugin,
    LoggerHandlerPlugin,
    MetricsPlugin,
    SecretProviderPlugin,
    TaskQueuePlugin,
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
    "CaptchaSolverPlugin",
    "TaskQueuePlugin",
    "BrowserStealthPlugin",
    "HttpBackendPlugin",
    "get_browser_stealth_plugins",
    "get_http_backend_plugin",
    "get_captcha_solver_plugin",
    "get_task_queue_plugin",
]

