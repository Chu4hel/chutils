from __future__ import annotations

import logging  # chutils: ignore[ChutilsIntegrationRule]
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


class CaptchaSolverPlugin(BasePlugin):
    """
    Интерфейс для плагина решения капч.
    Позволяет подключать кастомные/сторонние сервисы и ML-модели для капч.
    """

    @abstractmethod
    def solve_recaptcha(
        self,
        sitekey: str,
        page_url: str,
        timeout: float = 120.0,
        poll_interval: float = 5.0,
        **kwargs: Any,
    ) -> str:
        """Решает reCAPTCHA и возвращает g-recaptcha-response токен.

        Args:
            sitekey: Ключ сайта reCAPTCHA.
            page_url: URL страницы.
            timeout: Таймаут ожидания решения в секундах.
            poll_interval: Интервал опроса статуса решения.
            **kwargs: Дополнительные параметры.

        Returns:
            Строка ответа (g-recaptcha-response).
        """
        pass

    async def async_solve_recaptcha(
        self,
        sitekey: str,
        page_url: str,
        timeout: float = 120.0,
        poll_interval: float = 5.0,
        **kwargs: Any,
    ) -> str:
        """Асинхронно решает reCAPTCHA. По умолчанию вызывает синхронную версию.

        Args:
            sitekey: Ключ сайта reCAPTCHA.
            page_url: URL страницы.
            timeout: Таймаут ожидания решения в секундах.
            poll_interval: Интервал опроса статуса решения.
            **kwargs: Дополнительные параметры.

        Returns:
            Строка ответа.
        """
        import asyncio
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.solve_recaptcha(sitekey, page_url, timeout, poll_interval, **kwargs)
        )


class TaskQueuePlugin(BasePlugin):
    """
    Интерфейс для плагина очереди задач скрапинга.
    Позволяет подключать сторонние очереди (например, RabbitMQ, NATS, Kafka).
    """

    @abstractmethod
    def create_queue(self, name: str, **kwargs: Any) -> Any:
        """Создает и возвращает экземпляр очереди задач.

        Args:
            name: Имя очереди задач.
            **kwargs: Дополнительные параметры конфигурации очереди.

        Returns:
            Экземпляр очереди задач.
        """
        pass
