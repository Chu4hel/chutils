import pytest
from pydantic import BaseModel, Field

from chutils.config.generator import (
    generate_yaml_template,
    generate_env_template,
    generate_json_schema,
    PYDANTIC_AVAILABLE
)


class SubConfig(BaseModel):
    enabled: bool = Field(default=True, description="Включить подсистему")
    retries: int = 3


class MainConfig(BaseModel):
    app_name: str = Field(default="MyApp", description="Имя приложения")
    port: int = Field(default=8080)
    database: SubConfig = Field(description="Настройки БД")


@pytest.mark.skipif(not PYDANTIC_AVAILABLE, reason="Pydantic not installed")
def test_generate_yaml_template():
    yaml_out = generate_yaml_template(MainConfig)

    assert "# Имя приложения" in yaml_out
    assert 'app_name: "MyApp"' in yaml_out
    assert "port: 8080" in yaml_out
    assert "# Настройки БД" in yaml_out
    assert "database:" in yaml_out
    assert "  # Включить подсистему" in yaml_out
    assert "  enabled: true" in yaml_out
    assert "  retries: 3" in yaml_out


@pytest.mark.skipif(not PYDANTIC_AVAILABLE, reason="Pydantic not installed")
def test_generate_env_template():
    env_out = generate_env_template(MainConfig, prefix="MYAPP")

    assert "# Имя приложения" in env_out
    assert "MYAPP_APP_NAME=MyApp" in env_out
    assert "MYAPP_DATABASE_ENABLED=True" in env_out
    assert "MYAPP_DATABASE_RETRIES=3" in env_out


@pytest.mark.skipif(not PYDANTIC_AVAILABLE, reason="Pydantic not installed")
def test_generate_json_schema():
    schema_json = generate_json_schema(MainConfig)
    import json
    schema = json.loads(schema_json)

    assert schema["title"] == "MainConfig"
    assert "app_name" in schema["properties"]
    assert "database" in schema["properties"]
