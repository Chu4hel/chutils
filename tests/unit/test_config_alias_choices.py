"""
Тесты для поддержки Pydantic AliasChoices в get_config.
"""

import sys
from unittest.mock import patch

import pytest
from pydantic import AliasChoices, BaseModel, Field

from chutils.config import get_config, get_config_value
from chutils.exceptions import OptionalDependencyError


class DBConfig(BaseModel):
    url: str = Field(validation_alias=AliasChoices("DB_URL", "DATABASE_URL", "url"))
    max_connections: int = Field(default=10, validation_alias=AliasChoices("MAX_CONN", "max_conn"))


class AppConfig(BaseModel):
    app_name: str = Field(default="My App", validation_alias=AliasChoices("APP_NAME", "NAME"))
    port: int = Field(default=8080, validation_alias=AliasChoices("PORT", "SERVER_PORT"))
    db: DBConfig


def test_get_config_with_alias_choices(monkeypatch: pytest.MonkeyPatch) -> None:
    """Проверяет обогащение данных и парсинг Pydantic модели с AliasChoices из окружения."""
    monkeypatch.delenv("CH_DISABLE_ENV_OVERRIDE", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgres://user:pass@localhost:5432/mydb")
    monkeypatch.setenv("PORT", "9000")
    monkeypatch.setenv("MAX_CONN", "25")

    cfg = get_config(model=AppConfig)
    assert isinstance(cfg, AppConfig)
    assert cfg.port == 9000
    assert cfg.db.url == "postgres://user:pass@localhost:5432/mydb"
    assert cfg.db.max_connections == 25


def test_get_config_without_pydantic_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Проверяет выбрасывание OptionalDependencyError при отсутствии pydantic и передаче model."""
    with patch("chutils.env.has_pydantic", return_value=False):
        with pytest.raises(OptionalDependencyError) as exc_info:
            get_config(model=AppConfig)
        assert exc_info.value.context.get("dependency") == "pydantic"
