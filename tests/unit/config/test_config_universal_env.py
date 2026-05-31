import os

import pytest
from chutils.config import get_config_value, get_config_int, get_config_boolean


@pytest.fixture(autouse=True)
def clear_env():
    """Очищает переменные окружения и кэш конфигурации перед каждым тестом."""
    from chutils.config.manager import _cm
    _cm.clear_cache()
    
    keys_to_clear = [k for k in os.environ if k.startswith("CH_")]
    for k in keys_to_clear:
        del os.environ[k]
    yield


def test_universal_env_override_string(monkeypatch):
    """Проверяет переопределение строкового значения."""
    monkeypatch.setenv("CH_DATABASE_HOST", "prod-db")
    # Даже если в конфиге (которого может не быть) другое значение, ENV имеет приоритет
    val = get_config_value("Database", "host", fallback="localhost")
    assert val == "prod-db"


def test_universal_env_override_int(monkeypatch):
    """Проверяет переопределение целочисленного значения."""
    monkeypatch.setenv("CH_DATABASE_PORT", "9999")
    val = get_config_int("Database", "port", fallback=5432)
    assert val == 9999


def test_universal_env_override_boolean(monkeypatch):
    """Проверяет переопределение булева значения."""
    monkeypatch.setenv("CH_SERVER_DEBUG", "true")
    val = get_config_boolean("Server", "debug", fallback=False)
    assert val is True


def test_universal_env_override_disabled(monkeypatch):
    """Проверяет, что CH_DISABLE_ENV_OVERRIDE отключает механизм."""
    monkeypatch.setenv("CH_DATABASE_HOST", "prod-db")
    monkeypatch.setenv("CH_DISABLE_ENV_OVERRIDE", "true")
    val = get_config_value("Database", "host", fallback="localhost")
    assert val == "localhost"


def test_universal_env_override_no_prefix(monkeypatch):
    """Проверяет, что переменные без префикса CH_ игнорируются."""
    monkeypatch.setenv("DATABASE_HOST", "prod-db")
    val = get_config_value("Database", "host", fallback="localhost")
    assert val == "localhost"
