import pytest

from chutils import config
from chutils.config import get_config, get_config_value

try:
    from pydantic import BaseModel, Field

    PYDANTIC_INSTALLED = True
except ImportError:
    PYDANTIC_INSTALLED = False

    class BaseModel:
        pass

    def Field(*args, **kwargs):
        return None


pytestmark = pytest.mark.skipif(
    not PYDANTIC_INSTALLED, reason="Pydantic is required for these tests"
)


class TelegramConfig(BaseModel):
    bot_token: str


class DbConfig(BaseModel):
    host: str
    port: int = 5432


class PoolConfig(BaseModel):
    size: int = 10


class DatabaseSettings(BaseModel):
    pool: PoolConfig = Field(default_factory=PoolConfig)


class ServiceSettings(BaseModel):
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)


class MultiLevelConfig(BaseModel):
    service: ServiceSettings = Field(default_factory=ServiceSettings)


class AppConfig(BaseModel):
    telegram: TelegramConfig = Field(
        default_factory=lambda: TelegramConfig(bot_token="default")
    )
    database: DbConfig = Field(
        default_factory=lambda: DbConfig(host="localhost", port=5432)
    )


def test_env_double_underscore_without_yaml_section(config_fs, monkeypatch):
    """Тест: CH_TELEGRAM__BOT_TOKEN при отсутствии секции telegram в config.yml."""
    fs, project_root = config_fs
    fs.create_file(project_root / "config.yml", contents="app_name: MyTestApp\n")
    fs.create_file(project_root / "pyproject.toml", contents="")
    config._cm._reset()

    monkeypatch.setenv("CH_TELEGRAM__BOT_TOKEN", "123456:ABC")

    cfg = get_config(model=AppConfig)
    assert cfg.telegram.bot_token == "123456:ABC"


def test_env_double_underscore_nested_keys(config_fs, monkeypatch):
    """Тест: CH_DATABASE__HOST переопределяет хост во вложенной секции."""
    fs, project_root = config_fs
    fs.create_file(project_root / "config.yml", contents="")
    fs.create_file(project_root / "pyproject.toml", contents="")
    config._cm._reset()

    monkeypatch.setenv("CH_DATABASE__HOST", "postgres.remote")

    cfg = get_config(model=AppConfig)
    assert cfg.database.host == "postgres.remote"


def test_env_double_underscore_raw_dict(config_fs, monkeypatch):
    """Тест: парсер не добавляет ведущее подчеркивание к ключу без модели."""
    fs, project_root = config_fs
    fs.create_file(project_root / "config.yml", contents="")
    fs.create_file(project_root / "pyproject.toml", contents="")
    config._cm._reset()

    monkeypatch.setenv("CH_TELEGRAM__BOT_TOKEN", "token_value")

    raw_cfg = get_config()
    assert "telegram" in raw_cfg
    assert "bot_token" in raw_cfg["telegram"]
    assert "_bot_token" not in raw_cfg["telegram"]
    assert raw_cfg["telegram"]["bot_token"] == "token_value"


def test_env_double_underscore_multi_level(config_fs, monkeypatch):
    """Тест: многоуровневая вложенность CH_SERVICE__DATABASE__POOL__SIZE."""
    fs, project_root = config_fs
    fs.create_file(project_root / "config.yml", contents="")
    fs.create_file(project_root / "pyproject.toml", contents="")
    config._cm._reset()

    monkeypatch.setenv("CH_SERVICE__DATABASE__POOL__SIZE", "42")

    cfg = get_config(model=MultiLevelConfig)
    assert cfg.service.database.pool.size == 42


def test_env_single_underscore_with_model_fallback(config_fs, monkeypatch):
    """Тест: одиночное подчеркивание разрешается через known_sections модели, когда YAML пуст."""
    fs, project_root = config_fs
    fs.create_file(project_root / "config.yml", contents="")
    fs.create_file(project_root / "pyproject.toml", contents="")
    config._cm._reset()

    monkeypatch.setenv("CH_TELEGRAM_BOT_TOKEN", "single_underscore_token")

    cfg = get_config(model=AppConfig)
    assert cfg.telegram.bot_token == "single_underscore_token"


def test_env_double_underscore_extra_underscores_stripped(config_fs, monkeypatch):
    """Тест: стыковые подчеркивания корректно отсекаются (CH_TELEGRAM___BOT_TOKEN)."""
    fs, project_root = config_fs
    fs.create_file(project_root / "config.yml", contents="")
    fs.create_file(project_root / "pyproject.toml", contents="")
    config._cm._reset()

    monkeypatch.setenv("CH_TELEGRAM___BOT_TOKEN", "stripped_token")

    cfg = get_config(model=AppConfig)
    assert cfg.telegram.bot_token == "stripped_token"


def test_get_config_value_with_double_underscore(config_fs, monkeypatch):
    """Тест: get_config_value находит переменную с префиксом CH_SECTION__KEY."""
    fs, project_root = config_fs
    fs.create_file(project_root / "config.yml", contents="")
    fs.create_file(project_root / "pyproject.toml", contents="")
    config._cm._reset()

    monkeypatch.setenv("CH_TELEGRAM__BOT_TOKEN", "val_123")

    val = get_config_value("telegram", "bot_token")
    assert val == "val_123"


class TelegramAdminConfig(BaseModel):
    bot_token: str = "default_token"
    superadmin_ids: list[str] = Field(default_factory=list)


class AppAdminConfig(BaseModel):
    telegram: TelegramAdminConfig = Field(default_factory=TelegramAdminConfig)


def test_env_list_json_parsing_for_pydantic_model(config_fs, monkeypatch):
    """Тест: строка вида ['...'] из env парсится как list[str] и не вызывает ValidationError."""
    fs, project_root = config_fs
    fs.create_file(project_root / "config.yml", contents="")
    fs.create_file(project_root / "pyproject.toml", contents="")
    config._cm._reset()

    monkeypatch.setenv("CH_TELEGRAM__SUPERADMIN_IDS", '["123456789", "987654321"]')

    cfg = get_config(model=AppAdminConfig)
    assert isinstance(cfg.telegram.superadmin_ids, list)
    assert cfg.telegram.superadmin_ids == ["123456789", "987654321"]


def test_env_override_empty_string_in_yaml(config_fs, monkeypatch):
    """Тест: значение из переменной окружения перекрывает пустое значение из YAML (bot_token: '')."""
    fs, project_root = config_fs
    yaml_content = """
telegram:
  bot_token: ""
"""
    fs.create_file(project_root / "config.yml", contents=yaml_content)
    fs.create_file(project_root / "pyproject.toml", contents="")
    config._cm._reset()

    monkeypatch.setenv("CH_TELEGRAM__BOT_TOKEN", "live_token_from_env")

    cfg = get_config(model=AppConfig)
    assert cfg.telegram.bot_token == "live_token_from_env"


def test_get_config_list_with_env_json(config_fs, monkeypatch):
    """Тест: get_config_list корректно читает список из переменной окружения."""
    fs, project_root = config_fs
    fs.create_file(project_root / "config.yml", contents="")
    fs.create_file(project_root / "pyproject.toml", contents="")
    config._cm._reset()

    from chutils.config import get_config_list

    monkeypatch.setenv(
        "CH_TELEGRAM__PROXIES", '["http://proxy1:8080", "http://proxy2:8080"]'
    )

    proxies = get_config_list("telegram", "proxies")
    assert proxies == ["http://proxy1:8080", "http://proxy2:8080"]
