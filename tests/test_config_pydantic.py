import pytest

from chutils import config
from chutils.config import get_config, get_config_section

# Пытаемся импортировать pydantic для создания тестовых моделей
try:
    from pydantic import BaseModel, Field, ValidationError

    PYDANTIC_INSTALLED = True
except ImportError:
    PYDANTIC_INSTALLED = False


    # Заглушки для типов, чтобы тесты не падали на этапе импорта
    class BaseModel:
        pass


    class ValidationError(Exception):
        pass

# Пропускаем тесты, если pydantic не установлен (кроме теста на ImportError)
pytestmark = pytest.mark.skipif(not PYDANTIC_INSTALLED, reason="Pydantic is required for these tests")


class DbConfig(BaseModel):
    host: str
    port: int


class AppConfig(BaseModel):
    name: str
    version: str
    database: DbConfig = Field(alias="Database")


def test_get_config_with_model(config_fs):
    """Тест успешной валидации всего конфига через Pydantic модель."""
    fs, project_root = config_fs
    yaml_content = """
name: TestApp
version: 1.0.0
Database:
  host: localhost
  port: 5432
"""
    fs.create_file(project_root / "config.yml", contents=yaml_content)
    fs.create_file(project_root / "pyproject.toml", contents="")
    config._cm._reset()

    # ACT
    cfg = get_config(model=AppConfig)

    # ASSERT
    assert isinstance(cfg, AppConfig)
    assert cfg.name == "TestApp"
    assert cfg.database.host == "localhost"
    assert cfg.database.port == 5432


def test_get_config_section_with_model(config_fs):
    """Тест валидации отдельной секции через Pydantic модель."""
    fs, project_root = config_fs
    yaml_content = """
Database:
  host: remote-db
  port: 6432
"""
    fs.create_file(project_root / "config.yml", contents=yaml_content)
    fs.create_file(project_root / "pyproject.toml", contents="")
    config._cm._reset()

    # ACT
    db_cfg = get_config_section("Database", model=DbConfig)

    # ASSERT
    assert isinstance(db_cfg, DbConfig)
    assert db_cfg.host == "remote-db"
    assert db_cfg.port == 6432


def test_pydantic_validation_error(config_fs):
    """Тест выброса ValidationError при невалидных данных."""
    fs, project_root = config_fs
    yaml_content = """
Database:
  host: localhost
  port: "not-an-int"
"""
    fs.create_file(project_root / "config.yml", contents=yaml_content)
    fs.create_file(project_root / "pyproject.toml", contents="")
    config._cm._reset()

    # ACT & ASSERT
    with pytest.raises(ValidationError):
        get_config_section("Database", model=DbConfig)


def test_import_error_when_pydantic_missing(config_fs, monkeypatch):
    """Тест выброса понятной ошибки, если pydantic не установлен."""
    # Эмулируем отсутствие pydantic
    import sys

    # Сохраняем оригинал, если он есть
    original_pydantic = sys.modules.get('pydantic')

    try:
        # Эмулируем отсутствие pydantic через мок внутренней функции
        monkeypatch.setattr(config, '_check_pydantic', lambda: False)

        fs, project_root = config_fs
        fs.create_file(project_root / "config.yml", contents="key: value")
        config._cm._reset()

        # Создаем фиктивную модель (просто класс)
        class DummyModel:
            def __init__(self, **kwargs): pass

        with pytest.raises(ImportError, match="Pydantic is required"):
            get_config(model=DummyModel)

    finally:
        if original_pydantic:
            sys.modules['pydantic'] = original_pydantic
