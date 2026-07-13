from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

# Безопасный импорт базовых провайдеров
from chutils.config.providers import ConfigProvider
from chutils.metrics.base import MetricsProvider
from chutils.secret_manager.providers import SecretProvider


class BasePlugin(ABC):
    """
    Базовый абстрактный класс для всех плагинов chutils.
    Каждый плагин должен иметь уникальное имя.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Уникальное имя плагина.

        Returns:
            Имя плагина.
        """
        pass

    @property
    def version(self) -> str:
        """Версия плагина.

        Returns:
            Строка с версией плагина.
        """
        return "0.1.0"

    @property
    def description(self) -> str:
        """Описание плагина.

        Returns:
            Описание плагина.
        """
        return ""


class SecretProviderPlugin(BasePlugin, SecretProvider):
    """
    Интерфейс для плагина-провайдера секретов.
    Позволяет подключить стороннее хранилище секретов (например, AWS Secrets Manager, Vault).
    """
    pass


class ConfigProviderPlugin(BasePlugin, ConfigProvider):
    """
    Интерфейс для плагина-провайдера конфигураций.
    Позволяет загружать и сохранять конфигурации из внешних систем (например, Consul, Etcd).
    """
    pass


class LoggerHandlerPlugin(BasePlugin):
    """
    Интерфейс для плагина-обработчика логов.
    Позволяет добавлять кастомные logging.Handler в конфигурацию логирования.
    """

    @abstractmethod
    def get_handler(self, **kwargs: Any) -> logging.Handler:
        """Создает и возвращает настроенный экземпляр logging.Handler.
        
        Args:
            **kwargs: Параметры конфигурации для инициализации хэндлера.

        Returns:
            Настроенный объект logging.Handler.
        """
        pass


class MetricsPlugin(BasePlugin, MetricsProvider):
    """
    Интерфейс для плагина-провайдера метрик.
    Позволяет подключить стороннюю систему сбора метрик (например, Datadog, StatsD).
    """
    pass
