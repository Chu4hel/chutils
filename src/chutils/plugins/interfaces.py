from __future__ import annotations  # chutils: ignore[CodeDecompositionRule]

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


class ConfigProviderPlugin(BasePlugin, ConfigProvider):
    """
    Интерфейс для плагина-провайдера конфигураций.
    Позволяет загружать и сохранять конфигурации из внешних систем (например, Consul, Etcd).
    """


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


class MetricsPlugin(BasePlugin, MetricsProvider):
    """
    Интерфейс для плагина-провайдера метрик.
    Позволяет подключить стороннюю систему сбора метрик (например, Datadog, StatsD).
    """


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
            lambda: self.solve_recaptcha(
                sitekey, page_url, timeout, poll_interval, **kwargs
            ),
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


class BrowserStealthPlugin(BasePlugin):
    """
    Интерфейс для плагина глубокой маскировки и анонимизации браузера (Anti-Detect Stealth).
    Позволяет сторонним аддонам (например, chutils-stealth) подключать расширенную защиту
    от фингерпринтинга (AudioContext, WebRTC, Canvas, Client Hints, Fonts).
    """

    @abstractmethod
    def apply_playwright(self, context: Any, **kwargs: Any) -> None:
        """Применяет расширенные стелс-патчи к Playwright BrowserContext или Page.

        Args:
            context: Объект контекста браузера или страницы Playwright.
            **kwargs: Дополнительные параметры конфигурации маскировки.
        """

    @abstractmethod
    def apply_selenium(self, driver: Any, **kwargs: Any) -> None:
        """Применяет расширенные стелс-патчи к Selenium WebDriver.

        Args:
            driver: Экземпляр драйвера Selenium.
            **kwargs: Дополнительные параметры конфигурации маскировки.
        """

    @abstractmethod
    def apply_nodriver(self, tab: Any, **kwargs: Any) -> None:
        """Применяет расширенные стелс-патчи к nodriver Tab.

        Args:
            tab: Объект вкладки браузера nodriver.
            **kwargs: Дополнительные параметры конфигурации маскировки.
        """


class HttpBackendPlugin(BasePlugin):
    """
    Интерфейс для плагина кастомного сетевого бэкенда HTTP-клиента.
    Позволяет подключать альтернативные сетевые движки (например, curl_cffi с TLS/JA3/JA4 impersonation).
    """

    @abstractmethod
    def create_client(self, **kwargs: Any) -> Any:
        """Создает и возвращает синхронный HTTP-клиент или сессию.

        Args:
            **kwargs: Параметры конфигурации (базовый URL, заголовки, таймауты, impersonate и др.).

        Returns:
            Экземпляр HTTP-клиента.
        """

    @abstractmethod
    def create_async_client(self, **kwargs: Any) -> Any:
        """Создает и возвращает асинхронный HTTP-клиент или сессию.

        Args:
            **kwargs: Параметры конфигурации (базовый URL, заголовки, таймауты, impersonate и др.).

        Returns:
            Экземпляр асинхронного HTTP-клиента.
        """
