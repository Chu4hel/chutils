import os

from pydantic import BaseModel

from chutils.config import get_config, get_config_section, get_config_value, get_config_int, _cm


class TestModel(BaseModel):
    port: int
    host: str


def test_env_priority_in_pydantic_model(tmp_path, monkeypatch):
    """Проверка, что Pydantic модель получает значения из ENV (исправленный баг)."""
    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / "config.yml").write_text("server:\n  port: 8080\n  host: localhost")

    _cm._reset()
    os.chdir(project_root)

    # Устанавливаем ENV, который должен перекрыть файл
    monkeypatch.setenv("CH_SERVER_PORT", "9000")
    _cm.clear_cache()

    model = get_config_section("server", model=TestModel)
    assert model.port == 9000
    assert model.host == "localhost"


def test_ini_case_preservation(tmp_path):
    """Проверка сохранения регистра в INI файлах."""
    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / "config.ini").write_text("[Service]\nMyKey = True\nlowerkey = false")

    _cm._reset()
    os.chdir(project_root)

    config = get_config()
    section = config.get("Service", {})

    # Раньше MyKey стал бы mykey. Теперь регистр должен сохраняться.
    assert "MyKey" in section
    assert section["MyKey"] == "True"
    assert "lowerkey" in section


def test_case_insensitive_section_lookup():
    """Проверка регистронезависимого поиска секций."""
    config = {
        "Logging": {"level": "INFO"},
        "database": {"user": "admin"}
    }

    # Точное совпадение
    assert get_config_section("Logging", config=config)["level"] == "INFO"

    # Разный регистр
    assert get_config_section("logging", config=config)["level"] == "INFO"
    assert get_config_section("DATABASE", config=config)["user"] == "admin"


def test_env_override_with_case_mismatch(monkeypatch):
    """Проверка, что ENV перекрывает ключи даже при несовпадении регистра в запросе."""
    monkeypatch.setenv("CH_APP_PORT", "9999")
    _cm.clear_cache()

    # Запрашиваем в разном регистре
    assert get_config_value("app", "port") == "9999"
    assert get_config_value("APP", "PORT") == "9999"
    assert get_config_int("App", "Port") == 9999
