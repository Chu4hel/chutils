"""
Тесты для автоматического Fallback-поиска в окружении и маскирования секретов.
"""

import os
from unittest.mock import MagicMock, patch

import pytest

from chutils.config import get_config_boolean, get_config_int, get_config_value
from chutils.exceptions import ConfigKeyNotFoundError


def test_fallback_env_priority_chain(monkeypatch: pytest.MonkeyPatch) -> None:
    """Проверяет цепочку приоритетов CH_SECTION_KEY -> CH_KEY -> KEY."""
    monkeypatch.delenv("CH_DISABLE_ENV_OVERRIDE", raising=False)

    # 1. Проверяем fallback по KEY
    monkeypatch.setenv("DATABASE_URL", "postgres://localhost/db_key")
    val = get_config_value("Database", "database_url")
    assert val == "postgres://localhost/db_key"

    # 2. Проверяем приоритет CH_KEY над KEY
    monkeypatch.setenv("CH_DATABASE_URL", "postgres://localhost/db_ch_key")
    val = get_config_value("Database", "database_url")
    assert val == "postgres://localhost/db_ch_key"

    # 3. Проверяем приоритет CH_SECTION_KEY над CH_KEY и KEY
    monkeypatch.setenv("CH_DATABASE_DATABASE_URL", "postgres://localhost/db_section_key")
    val = get_config_value("Database", "database_url")
    assert val == "postgres://localhost/db_section_key"


def test_fallback_env_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Проверяет отключение fallback при CH_DISABLE_ENV_OVERRIDE=true."""
    monkeypatch.setenv("CH_DISABLE_ENV_OVERRIDE", "true")
    monkeypatch.setenv("DATABASE_PORT", "5432")

    val = get_config_value("Database", "database_port", fallback=3306)
    assert val == 3306

    with pytest.raises(ConfigKeyNotFoundError):
        get_config_value("Database", "database_port", required=True)


def test_fallback_env_secrets_masking(monkeypatch: pytest.MonkeyPatch) -> None:
    """Проверяет автоматическое регистрацию маски в логгере при поиске секретов через fallback."""
    monkeypatch.delenv("CH_DISABLE_ENV_OVERRIDE", raising=False)
    monkeypatch.setenv("API_SECRET_KEY", "super_secret_token_123")

    with patch("chutils.logger.setup_logger") as mock_setup_logger:
        mock_logger = MagicMock()
        mock_setup_logger.return_value = mock_logger

        val = get_config_value("Secrets", "api_secret_key")
        assert val == "super_secret_token_123"

        # Проверяем, что add_mask вызывался с найденным секретом
        mock_logger.add_mask.assert_called_with("super_secret_token_123")


def test_fallback_typed_getters(monkeypatch: pytest.MonkeyPatch) -> None:
    """Проверяет работу типизированных геттеров с fallback в окружение."""
    monkeypatch.delenv("CH_DISABLE_ENV_OVERRIDE", raising=False)
    monkeypatch.setenv("SERVER_PORT", "8080")
    monkeypatch.setenv("ENABLE_FEATURE", "true")

    port = get_config_int("Server", "server_port")
    assert port == 8080

    enabled = get_config_boolean("Features", "enable_feature")
    assert enabled is True
