"""
Unit-тесты для Custom Config Providers API (chutils.config.custom_providers).

Покрывают:
- DictConfigProvider — базовые сценарии.
- Приоритизацию провайдеров (_CustomProviderRegistry).
- Интеграцию с get_config_value (провайдер перекрывает файловые данные).
- Асинхронный aget_config_value.
- Симуляцию сетевой задержки в провайдере.
- reset_providers / reset() реестра.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from chutils.config.custom_providers import (
    BaseConfigProvider,
    DictConfigProvider,
    _CustomProviderRegistry,
    get_registry,
)


# ---------------------------------------------------------------------------
# Вспомогательные фикстуры
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clean_registry():
    """Сбрасываем глобальный реестр до и после каждого теста."""
    get_registry().reset()
    yield
    get_registry().reset()


# ---------------------------------------------------------------------------
# DictConfigProvider
# ---------------------------------------------------------------------------

class TestDictConfigProvider:
    """Тесты для DictConfigProvider."""

    def test_get_value_returns_existing(self):
        provider = DictConfigProvider({"database": {"host": "localhost", "port": "5432"}})
        assert provider.get_value("database", "host") == "localhost"
        assert provider.get_value("database", "port") == "5432"

    def test_get_value_returns_none_for_missing_key(self):
        provider = DictConfigProvider({"database": {"host": "localhost"}})
        assert provider.get_value("database", "missing_key") is None

    def test_get_value_returns_none_for_missing_section(self):
        provider = DictConfigProvider({"database": {"host": "localhost"}})
        assert provider.get_value("missing_section", "host") is None

    def test_case_insensitive_section(self):
        provider = DictConfigProvider({"Database": {"host": "localhost"}})
        assert provider.get_value("database", "host") == "localhost"
        assert provider.get_value("DATABASE", "host") == "localhost"
        assert provider.get_value("DataBase", "host") == "localhost"

    def test_case_insensitive_key(self):
        provider = DictConfigProvider({"db": {"MaxRetries": "3"}})
        assert provider.get_value("db", "maxretries") == "3"
        assert provider.get_value("db", "MAXRETRIES") == "3"
        assert provider.get_value("db", "MaxRetries") == "3"

    def test_value_types_preserved(self):
        provider = DictConfigProvider({"app": {"port": 8080, "debug": True, "rate": 1.5}})
        assert provider.get_value("app", "port") == 8080
        assert provider.get_value("app", "debug") is True
        assert provider.get_value("app", "rate") == 1.5

    @pytest.mark.asyncio
    async def test_aget_value_returns_existing(self):
        provider = DictConfigProvider({"app": {"name": "myapp"}})
        result = await provider.aget_value("app", "name")
        assert result == "myapp"

    @pytest.mark.asyncio
    async def test_aget_value_returns_none_for_missing(self):
        provider = DictConfigProvider({"app": {"name": "myapp"}})
        result = await provider.aget_value("app", "missing")
        assert result is None

    def test_empty_data(self):
        provider = DictConfigProvider({})
        assert provider.get_value("any", "key") is None


# ---------------------------------------------------------------------------
# BaseConfigProvider — абстрактный интерфейс
# ---------------------------------------------------------------------------

class TestBaseConfigProvider:
    """Тесты на соблюдение контракта BaseConfigProvider."""

    def test_cannot_instantiate_abstract(self):
        with pytest.raises(TypeError):
            BaseConfigProvider()  # type: ignore[abstract]

    def test_must_implement_get_value(self):
        class IncompleteProvider(BaseConfigProvider):
            async def aget_value(self, section: str, key: str) -> Any | None:
                return None
            # get_value не реализован

        with pytest.raises(TypeError):
            IncompleteProvider()  # type: ignore[abstract]

    def test_must_implement_aget_value(self):
        class IncompleteProvider(BaseConfigProvider):
            def get_value(self, section: str, key: str) -> Any | None:
                return None
            # aget_value не реализован

        with pytest.raises(TypeError):
            IncompleteProvider()  # type: ignore[abstract]

    def test_concrete_implementation_works(self):
        class ConcreteProvider(BaseConfigProvider):
            def get_value(self, section: str, key: str) -> Any | None:
                return f"{section}.{key}"

            async def aget_value(self, section: str, key: str) -> Any | None:
                return self.get_value(section, key)

        p = ConcreteProvider()
        assert p.get_value("sec", "key") == "sec.key"


# ---------------------------------------------------------------------------
# _CustomProviderRegistry — приоритизация
# ---------------------------------------------------------------------------

class TestCustomProviderRegistry:
    """Тесты для реестра провайдеров."""

    def _make_registry(self) -> _CustomProviderRegistry:
        """Создает изолированный реестр (не глобальный)."""
        return _CustomProviderRegistry()

    def test_register_and_get_value(self):
        registry = self._make_registry()
        provider = DictConfigProvider({"db": {"host": "myhost"}})
        registry.register(provider, priority=100)
        assert registry.get_value("db", "host") == "myhost"

    def test_returns_none_when_no_providers(self):
        registry = self._make_registry()
        assert registry.get_value("any", "key") is None

    def test_returns_none_when_key_not_found(self):
        registry = self._make_registry()
        registry.register(DictConfigProvider({"db": {"host": "x"}}))
        assert registry.get_value("db", "missing") is None

    def test_priority_lower_number_wins(self):
        """Провайдер с меньшим priority опрашивается первым и побеждает."""
        registry = self._make_registry()

        low_priority = DictConfigProvider({"app": {"name": "from-low-priority"}})
        high_priority = DictConfigProvider({"app": {"name": "from-high-priority"}})

        registry.register(low_priority, priority=200)
        registry.register(high_priority, priority=10)

        result = registry.get_value("app", "name")
        assert result == "from-high-priority"

    def test_priority_equal_first_registered_wins(self):
        """При одинаковом приоритете побеждает первый зарегистрированный."""
        registry = self._make_registry()

        first = DictConfigProvider({"app": {"name": "first"}})
        second = DictConfigProvider({"app": {"name": "second"}})

        registry.register(first, priority=50)
        registry.register(second, priority=50)

        result = registry.get_value("app", "name")
        assert result == "first"

    def test_fallback_to_next_provider(self):
        """Если первый провайдер вернул None — опрашивается следующий."""
        registry = self._make_registry()

        no_answer = DictConfigProvider({"app": {}})  # не знает про ключ
        has_answer = DictConfigProvider({"app": {"key": "value"}})

        registry.register(no_answer, priority=10)
        registry.register(has_answer, priority=50)

        result = registry.get_value("app", "key")
        assert result == "value"

    def test_reset_clears_all_providers(self):
        registry = self._make_registry()
        registry.register(DictConfigProvider({"app": {"key": "val"}}))
        assert len(registry) == 1

        registry.reset()
        assert len(registry) == 0
        assert registry.get_value("app", "key") is None

    def test_provider_error_does_not_crash_registry(self):
        """Исключение в провайдере логируется, а не пробрасывается выше."""
        registry = self._make_registry()

        broken = MagicMock(spec=BaseConfigProvider)
        broken.get_value.side_effect = RuntimeError("DB connection failed")
        registry.register(broken, priority=10)

        good = DictConfigProvider({"app": {"key": "fallback"}})
        registry.register(good, priority=50)

        result = registry.get_value("app", "key")
        assert result == "fallback"

    @pytest.mark.asyncio
    async def test_aget_value_priority(self):
        registry = self._make_registry()

        low = DictConfigProvider({"app": {"x": "low"}})
        high = DictConfigProvider({"app": {"x": "high"}})

        registry.register(low, priority=100)
        registry.register(high, priority=5)

        result = await registry.aget_value("app", "x")
        assert result == "high"

    @pytest.mark.asyncio
    async def test_aget_value_returns_none_when_empty(self):
        registry = self._make_registry()
        result = await registry.aget_value("any", "key")
        assert result is None

    @pytest.mark.asyncio
    async def test_aget_value_error_falls_back(self):
        registry = self._make_registry()

        broken = MagicMock(spec=BaseConfigProvider)
        broken.aget_value = AsyncMock(side_effect=RuntimeError("async failure"))
        registry.register(broken, priority=10)

        good = DictConfigProvider({"app": {"k": "v"}})
        registry.register(good, priority=50)

        result = await registry.aget_value("app", "k")
        assert result == "v"


# ---------------------------------------------------------------------------
# Интеграция с get_config_value
# ---------------------------------------------------------------------------

class TestGetConfigValueIntegration:
    """Тесты интеграции провайдеров с get_config_value."""

    def test_provider_overrides_file_config(self):
        """Провайдер перекрывает данные из файлов."""
        from chutils.config import get_config_value, register_provider

        mock_config = {"database": {"host": "file-host", "port": "5432"}}

        provider = DictConfigProvider({"database": {"host": "provider-host"}})
        register_provider(provider, priority=10)

        # Передаём mock_config как «данные из файла»
        result = get_config_value("database", "host", config=mock_config)
        assert result == "provider-host"

    def test_fallback_to_file_when_provider_returns_none(self):
        """Если провайдер не знает ключа — берём из файла."""
        from chutils.config import get_config_value, register_provider

        mock_config = {"database": {"host": "file-host", "port": "5432"}}

        # Провайдер знает только другой ключ
        provider = DictConfigProvider({"database": {"other": "x"}})
        register_provider(provider, priority=10)

        result = get_config_value("database", "host", config=mock_config)
        assert result == "file-host"

    def test_without_providers_reads_from_config(self):
        """Без провайдеров — стандартное поведение."""
        from chutils.config import get_config_value

        mock_config = {"app": {"name": "myapp"}}
        result = get_config_value("app", "name", config=mock_config)
        assert result == "myapp"

    def test_multiple_providers_priority(self):
        """Несколько провайдеров — побеждает с наименьшим priority."""
        from chutils.config import get_config_value, register_provider

        provider_low = DictConfigProvider({"app": {"env": "staging"}})
        provider_high = DictConfigProvider({"app": {"env": "production"}})

        register_provider(provider_low, priority=100)
        register_provider(provider_high, priority=5)

        result = get_config_value("app", "env", config={})
        assert result == "production"


# ---------------------------------------------------------------------------
# Асинхронные провайдеры с симуляцией сетевой задержки
# ---------------------------------------------------------------------------

class TestAsyncProviderWithDelay:
    """Тесты асинхронных провайдеров с имитацией сетевой задержки."""

    @pytest.mark.asyncio
    async def test_async_provider_with_delay(self):
        """Провайдер с задержкой (имитация сетевого запроса) работает корректно."""

        class SlowNetworkProvider(BaseConfigProvider):
            def __init__(self, delay: float, data: dict[str, dict[str, Any]]) -> None:
                self._delay = delay
                self._inner = DictConfigProvider(data)

            def get_value(self, section: str, key: str) -> Any | None:
                time.sleep(self._delay)
                return self._inner.get_value(section, key)

            async def aget_value(self, section: str, key: str) -> Any | None:
                await asyncio.sleep(self._delay)
                return self._inner.get_value(section, key)

        registry = _CustomProviderRegistry()
        provider = SlowNetworkProvider(
            delay=0.05,
            data={"remote": {"api_key": "secret-123"}},
        )
        registry.register(provider, priority=10)

        start = time.monotonic()
        result = await registry.aget_value("remote", "api_key")
        elapsed = time.monotonic() - start

        assert result == "secret-123"
        assert elapsed >= 0.04, "Задержка должна присутствовать"

    @pytest.mark.asyncio
    async def test_aget_config_value_uses_async_providers(self):
        """aget_config_value корректно вызывает асинхронные методы провайдеров."""
        from chutils.config import aget_config_value, register_provider

        provider = DictConfigProvider({"remote": {"token": "async-token-456"}})
        register_provider(provider, priority=1)

        result = await aget_config_value("remote", "token", config={})
        assert result == "async-token-456"

    @pytest.mark.asyncio
    async def test_aget_config_value_fallback_to_sync(self):
        """aget_config_value возвращает данные из файлового кэша, если провайдеры не ответили."""
        from chutils.config import aget_config_value

        mock_config = {"service": {"url": "http://localhost"}}
        result = await aget_config_value("service", "url", config=mock_config)
        assert result == "http://localhost"

    @pytest.mark.asyncio
    async def test_aget_config_value_default_fallback(self):
        """aget_config_value возвращает fallback, если ключ нигде не найден."""
        from chutils.config import aget_config_value

        result = await aget_config_value("missing", "key", fallback="default", config={})
        assert result == "default"


# ---------------------------------------------------------------------------
# reset_providers (публичное API)
# ---------------------------------------------------------------------------

class TestResetProviders:
    """Тесты функции reset_providers."""

    def test_reset_clears_global_registry(self):
        from chutils.config import get_config_value, register_provider, reset_providers

        provider = DictConfigProvider({"sec": {"k": "v"}})
        register_provider(provider)

        # Провайдер работает
        assert get_config_value("sec", "k", config={}) == "v"

        reset_providers()

        # После сброса — провайдер не используется
        assert get_config_value("sec", "k", fallback="gone", config={}) == "gone"
