import json
import os
from pathlib import Path

import pytest

from chutils.config import (
    get_config,
    _initialize_paths,
    save_config_value,
    get_config_file_path
)


@pytest.fixture(autouse=True)
def reset_config_state():
    """Сбрасывает глобальное состояние модуля config перед каждым тестом."""
    import chutils.config
    chutils.config._cm._reset()
    yield


def test_json_config_auto_discovery(fs):
    """Тест автоматического обнаружения config.json."""
    # Используем абсолютный путь, подходящий для платформы
    root_path = "/app" if os.name != 'nt' else "C:/app"
    fs.create_dir(root_path)
    fs.create_file(os.path.join(root_path, "pyproject.toml"))
    fs.create_file(os.path.join(root_path, "config.json"), contents='{"section": {"key": "value"}}')

    fs.cwd = root_path

    _initialize_paths()
    config_file_path = get_config_file_path()
    assert config_file_path is not None
    assert Path(config_file_path).name == "config.json"


def test_json_config_loading(fs):
    """Тест загрузки данных из config.json."""
    root_path = "/app" if os.name != 'nt' else "C:/app"
    fs.create_file(os.path.join(root_path, "pyproject.toml"))
    fs.create_file(os.path.join(root_path, "config.json"), contents='{"Section1": {"key1": "val1"}}')
    fs.cwd = root_path

    config = get_config()
    assert config["Section1"]["key1"] == "val1"


def test_json_local_override(fs):
    """Тест переопределения через config.local.json."""
    root_path = "/app" if os.name != 'nt' else "C:/app"
    fs.create_file(os.path.join(root_path, "pyproject.toml"))
    fs.create_file(os.path.join(root_path, "config.json"),
                   contents='{"Section1": {"key1": "original", "key2": "keep"}}')
    fs.create_file(os.path.join(root_path, "config.local.json"), contents='{"Section1": {"key1": "overridden"}}')
    fs.cwd = root_path

    config = get_config()
    assert config["Section1"]["key1"] == "overridden"
    assert config["Section1"]["key2"] == "keep"


def test_save_config_value_json(fs):
    """Тест сохранения значения в JSON файл."""
    root_path = "/app" if os.name != 'nt' else "C:/app"
    config_path = os.path.join(root_path, "config.json")
    fs.create_file(os.path.join(root_path, "pyproject.toml"))
    fs.create_file(config_path, contents='{"Section1": {"key1": "old_val"}}')
    fs.cwd = root_path

    # Инициализируем пути
    _initialize_paths()

    success = save_config_value("Section1", "key1", "new_val")
    assert success is True

    with open(config_path, "r") as f:
        data = json.load(f)
    assert data["Section1"]["key1"] == "new_val"


def test_invalid_json_handling(fs, caplog):
    """Тест обработки некорректного JSON."""
    root_path = "/app" if os.name != 'nt' else "C:/app"
    fs.create_file(os.path.join(root_path, "pyproject.toml"))
    fs.create_file(os.path.join(root_path, "config.json"), contents='{"invalid": json')
    fs.cwd = root_path

    config = get_config()
    assert config == {}
    assert "Ошибка чтения" in caplog.text
