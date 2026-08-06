"""
API для кастомных динамических провайдеров конфигурации.

Позволяет регистрировать внешние источники настроек (БД, Key-Value хранилища,
удалённые API) и интегрировать их в единый интерфейс ``chutils.config``.

Пример использования::

    from chutils.config import register_provider
    from chutils.config.custom_providers import DictConfigProvider

    provider = DictConfigProvider({"database": {"host": "localhost"}})
    register_provider(provider, priority=10)
"""

from __future__ import annotations

import logging  # chutils: ignore[ChutilsIntegrationRule]
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)  # chutils: ignore[ChutilsIntegrationRule]
"""Локальный логгер модуля."""


class BaseConfigProvider(ABC):
    """Абстрактный базовый класс для кастомного динамического провайдера конфигурации.

    Реализуйте этот класс, чтобы интегрировать любой внешний источник настроек
    (БД, Redis, Consul, удалённый API и т.д.) в систему конфигурации ``chutils``.

    Провайдеры опрашиваются **перед** чтением локальных файлов конфигурации:
    если провайдер вернул значение (не ``None``), оно используется без обращения
    к файлам.

    Приоритет между несколькими провайдерами определяется параметром ``priority``
    при регистрации: **меньшее число → больший приоритет** (аналогично DNS TTL).

    Example:
        Минимальная реализация синхронного провайдера::

            class EnvVaultProvider(BaseConfigProvider):
                def get_value(self, section: str, key: str) -> Any | None:
                    return vault_client.get(f"{section}/{key}")

                async def aget_value(self, section: str, key: str) -> Any | None:
                    return await async_vault_client.get(f"{section}/{key}")
    """

    @abstractmethod
    def get_value(self, section: str, key: str) -> Any | None:
        """Синхронно получает значение из провайдера.

        Args:
            section: Имя секции конфигурации.
            key: Имя ключа внутри секции.

        Returns:
            Значение из источника или ``None``, если ключ не найден.
        """

    @abstractmethod
    async def aget_value(self, section: str, key: str) -> Any | None:
        """Асинхронно получает значение из провайдера.

        Args:
            section: Имя секции конфигурации.
            key: Имя ключа внутри секции.

        Returns:
            Значение из источника или ``None``, если ключ не найден.
        """


class DictConfigProvider(BaseConfigProvider):
    """Провайдер конфигурации на основе словаря в памяти.

    Предназначен для использования в тестах (моки настроек) и для быстрого
    прототипирования. Полностью потокобезопасен при чтении, так как словарь
    не изменяется после инициализации.

    Example:
        Использование в тестах с ``pytest``::

            import pytest
            from chutils.config import register_provider, reset_providers
            from chutils.config.custom_providers import DictConfigProvider

            @pytest.fixture(autouse=True)
            def mock_config():
                provider = DictConfigProvider({
                    "database": {"host": "test-host", "port": "5432"},
                    "app": {"debug": "true"},
                })
                register_provider(provider, priority=0)
                yield
                reset_providers()

    Attributes:
        _data: Вложенный словарь вида ``{section: {key: value}}``.
    """

    def __init__(self, data: dict[str, dict[str, Any]]) -> None:
        """Инициализирует провайдер с заданным словарём.

        Args:
            data: Вложенный словарь вида ``{section: {key: value}}``.
                  Ключи секций и ключей сравниваются без учёта регистра.
        """
        # Нормализуем ключи в нижний регистр для регистронезависимого поиска
        self._data: dict[str, dict[str, Any]] = {
            sec.lower(): {k.lower(): v for k, v in keys.items()}
            for sec, keys in data.items()
        }

    def get_value(self, section: str, key: str) -> Any | None:
        """Синхронно возвращает значение из словаря.

        Args:
            section: Имя секции (без учёта регистра).
            key: Имя ключа (без учёта регистра).

        Returns:
            Значение или ``None``, если секция или ключ не найдены.
        """
        section_data = self._data.get(section.lower())
        if section_data is None:
            return None
        return section_data.get(key.lower())

    async def aget_value(self, section: str, key: str) -> Any | None:
        """Асинхронно возвращает значение из словаря.

        Реализация не блокирует event loop, поскольку работает только
        с данными в памяти.

        Args:
            section: Имя секции (без учёта регистра).
            key: Имя ключа (без учёта регистра).

        Returns:
            Значение или ``None``, если секция или ключ не найдены.
        """
        return self.get_value(section, key)


class _ProviderEntry:
    """Внутренняя запись реестра провайдеров.

    Attributes:
        provider: Экземпляр провайдера.
        priority: Приоритет (меньше → выше).
    """

    __slots__ = ("provider", "priority")

    def __init__(self, provider: BaseConfigProvider, priority: int) -> None:
        self.provider = provider
        self.priority = priority

    def __lt__(self, other: _ProviderEntry) -> bool:
        return self.priority < other.priority


class _CustomProviderRegistry:
    """Потокобезопасный реестр кастомных провайдеров конфигурации.

    Является синглтоном, хранящим зарегистрированные провайдеры в порядке
    их приоритета. Используется внутренними функциями ``chutils.config``.
    """

    def __init__(self) -> None:
        import threading
        self._lock = threading.RLock()
        self._entries: list[_ProviderEntry] = []

    def register(self, provider: BaseConfigProvider, priority: int = 100) -> None:
        """Регистрирует провайдер с указанным приоритетом.

        Args:
            provider: Экземпляр, реализующий :class:`BaseConfigProvider`.
            priority: Числовой приоритет. Меньшее значение → выше приоритет
                (провайдер опрашивается первым). По умолчанию: 100.
        """
        with self._lock:
            self._entries.append(_ProviderEntry(provider, priority))
            self._entries.sort()
            logger.debug(
                "Зарегистрирован кастомный провайдер %s с приоритетом %d",
                type(provider).__name__,
                priority,
            )

    def get_value(self, section: str, key: str) -> Any | None:
        """Опрашивает провайдеры по убыванию приоритета (синхронно).

        Возвращает первое не-``None`` значение.

        Args:
            section: Имя секции конфигурации.
            key: Имя ключа.

        Returns:
            Значение от первого ответившего провайдера или ``None``.
        """
        with self._lock:
            entries = list(self._entries)

        for entry in entries:
            try:
                value = entry.provider.get_value(section, key)
                if value is not None:
                    logger.debug(
                        "Провайдер %s вернул значение для [%s].%s",
                        type(entry.provider).__name__,
                        section,
                        key,
                    )
                    return value
            except Exception as exc:
                logger.error(
                    "Ошибка в провайдере %s при получении [%s].%s: %s",
                    type(entry.provider).__name__,
                    section,
                    key,
                    exc,
                )
        return None

    async def aget_value(self, section: str, key: str) -> Any | None:
        """Асинхронно опрашивает провайдеры по убыванию приоритета.

        Возвращает первое не-``None`` значение.

        Args:
            section: Имя секции конфигурации.
            key: Имя ключа.

        Returns:
            Значение от первого ответившего провайдера или ``None``.
        """
        with self._lock:
            entries = list(self._entries)

        for entry in entries:
            try:
                value = await entry.provider.aget_value(section, key)
                if value is not None:
                    logger.debug(
                        "Провайдер %s (async) вернул значение для [%s].%s",
                        type(entry.provider).__name__,
                        section,
                        key,
                    )
                    return value
            except Exception as exc:
                logger.error(
                    "Ошибка в провайдере %s (async) при получении [%s].%s: %s",
                    type(entry.provider).__name__,
                    section,
                    key,
                    exc,
                )
        return None

    def reset(self) -> None:
        """Очищает реестр провайдеров.

        Используется в тестах для сброса состояния между тест-кейсами.
        """
        with self._lock:
            self._entries.clear()
            logger.debug("Реестр кастомных провайдеров очищен.")

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)


_registry = _CustomProviderRegistry()
"Глобальный реестр кастомных провайдеров"


def get_registry() -> _CustomProviderRegistry:
    """Возвращает глобальный реестр кастомных провайдеров.

    Returns:
        Глобальный экземпляр :class:`_CustomProviderRegistry`.
    """
    return _registry
