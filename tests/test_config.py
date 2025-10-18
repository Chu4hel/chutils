# -*- coding: utf-8 -*-
import pytest
from pathlib import Path
from chutils import config

# Контент для фейкового config.yml
FAKE_YAML_CONTENT = """
Database:
  host: localhost
  port: 5432
  enable_ssl: true
  timeout: 15.5

User:
  name: Admin
  roles:
    - admin
    - editor
    - viewer
"""

# Контент для фейкового config.ini для теста на обратную совместимость
FAKE_INI_CONTENT = """
[Database]
host = localhost_ini
port = 1234
"""


@pytest.fixture
def config_fs(fs):  # fs - это фикстура из pyfakefs
    """
    Настраивает фейковую файловую систему и сбрасывает состояние модуля config.
    """
    # 1. Сброс состояния модуля
    config._BASE_DIR = None
    config._CONFIG_FILE_PATH = None
    config._paths_initialized = False
    config._config_object = None
    config._config_loaded = False

    # 2. Создание файловой структуры
    project_root = Path("/home/user/project")
    src_path = project_root / "src" / "app"
    fs.create_dir(src_path)

    # 3. Установка текущей директории
    import os
    os.chdir(src_path)

    # Передаем управление тесту
    yield fs, project_root

    # 4. Очистка
    os.chdir("/")


def test_finds_yaml_first(config_fs):
    """Проверяет, что config.yml находится в приоритете."""
    fs, project_root = config_fs
    # Создаем оба файла: и .yml, и .ini
    fs.create_file(project_root / "config.yml", contents=FAKE_YAML_CONTENT)
    fs.create_file(project_root / "config.ini", contents=FAKE_INI_CONTENT)

    # ACT
    config._initialize_paths()

    # ASSERT
    assert Path(config._CONFIG_FILE_PATH).as_posix().endswith('/home/user/project/config.yml')

    # ACT & ASSERT: Проверяем, что загрузились данные из YAML
    db_host = config.get_config_value("Database", "host")
    assert db_host == "localhost"


def test_falls_back_to_ini(config_fs):
    """Проверяет, что если нет config.yml, используется config.ini."""
    fs, project_root = config_fs
    # Создаем только .ini файл
    fs.create_file(project_root / "config.ini", contents=FAKE_INI_CONTENT)

    # ACT
    config._initialize_paths()

    # ASSERT
    assert Path(config._CONFIG_FILE_PATH).as_posix().endswith('/home/user/project/config.ini')

    # ACT & ASSERT: Проверяем, что загрузились данные из INI
    db_host = config.get_config_value("Database", "host")
    assert db_host == "localhost_ini"
    port = config.get_config_int("Database", "port")
    assert port == 1234


def test_get_config_typed_values_from_yaml(config_fs):
    """Тестирует чтение типизированных значений из YAML."""
    fs, project_root = config_fs
    fs.create_file(project_root / "config.yml", contents=FAKE_YAML_CONTENT)

    # PyYAML автоматически преобразует типы, наши функции должны это поддерживать
    assert config.get_config_int("Database", "port") == 5432
    assert config.get_config_float("Database", "timeout") == 15.5
    assert config.get_config_boolean("Database", "enable_ssl") is True


def test_get_config_list_from_yaml(config_fs):
    """Тестирует чтение списка из YAML."""
    fs, project_root = config_fs
    fs.create_file(project_root / "config.yml", contents=FAKE_YAML_CONTENT)

    roles = config.get_config_list("User", "roles")
    assert roles == ["admin", "editor", "viewer"]


def test_get_config_section_from_yaml(config_fs):
    """Тестирует получение целой секции из YAML как словаря."""
    fs, project_root = config_fs
    fs.create_file(project_root / "config.yml", contents=FAKE_YAML_CONTENT)

    db_section = config.get_config_section("Database")
    assert db_section == {
        "host": "localhost",
        "port": 5432,  # PyYAML парсит как int
        "enable_ssl": True,
        "timeout": 15.5
    }


def test_save_config_value_on_ini(config_fs):
    """Проверяет, что сохранение значения в .ini файл работает."""
    fs, project_root = config_fs
    ini_path = project_root / "config.ini"
    fs.create_file(ini_path, contents=FAKE_INI_CONTENT)

    # ACT: Сохраняем новое значение, используя явный путь к файлу
    success = config.save_config_value("Database", "host", "new.host.com", cfg_file=str(ini_path))
    assert success is True

    # ASSERT: Проверяем, что содержимое файла изменилось
    with open(ini_path) as f:
        content = f.read()
    assert "host = new.host.com" in content


def test_save_config_value_updates_yaml(config_fs):
    """Проверяет, что сохранение в .yml файл обновляет существующий ключ."""
    fs, project_root = config_fs
    yaml_path = project_root / "config.yml"
    fs.create_file(yaml_path, contents=FAKE_YAML_CONTENT)

    # ACT: Пытаемся обновить значение в .yml файле
    success = config.save_config_value("Database", "host", "new.db.host.com", cfg_file=str(yaml_path))
    assert success is True

    # ASSERT: Проверяем, что значение в файле изменилось
    import yaml
    with open(yaml_path) as f:
        data = yaml.safe_load(f)

    assert data["Database"]["host"] == "new.db.host.com"
    # Убедимся, что другие данные не пострадали
    assert data["Database"]["port"] == 5432


def test_save_config_value_adds_to_yaml(config_fs):
    """Проверяет, что сохранение в .yml файл добавляет новый ключ и секцию."""
    fs, project_root = config_fs
    yaml_path = project_root / "config.yml"
    fs.create_file(yaml_path, contents=FAKE_YAML_CONTENT)

    # ACT: Добавляем новый ключ в существующую секцию
    success_add_key = config.save_config_value("Database", "new_key", "new_value", cfg_file=str(yaml_path))
    assert success_add_key is True

    # ACT: Добавляем новую секцию с ключом
    success_add_section = config.save_config_value("NewSection", "some_key", True, cfg_file=str(yaml_path))
    assert success_add_section is True

    # ASSERT: Проверяем, что все данные корректно добавились
    import yaml
    with open(yaml_path) as f:
        data = yaml.safe_load(f)

    assert data["Database"]["new_key"] == "new_value"
    assert data["NewSection"]["some_key"] is True


def test_save_config_adds_new_key_to_ini(config_fs):
    """Проверяет, что функция добавляет новый ключ в .ini файл, если он не существует."""
    fs, project_root = config_fs
    ini_path = project_root / "config.ini"
    # Используем контент без ключа 'user'
    content = """[Database]
host = localhost_ini
port = 1234

[User]
"""
    fs.create_file(ini_path, contents=content)

    # ACT: Сохраняем новый ключ 'user' в секцию 'Database'
    success = config.save_config_value("Database", "user", "test_user", cfg_file=str(ini_path))
    assert success is True

    # ASSERT: Проверяем, что содержимое файла изменилось и новый ключ добавлен
    with open(ini_path) as f:
        file_content = f.read()

    assert "user = test_user" in file_content
    # Проверяем, что старые данные остались на месте
    assert "host = localhost_ini" in file_content


def test_save_config_adds_new_section_to_ini(config_fs):
    """Проверяет, что функция добавляет новую секцию в .ini файл, если она не существует."""
    fs, project_root = config_fs
    ini_path = project_root / "config.ini"
    # Используем контент только с одной секцией
    content = """[Database]
host = localhost_ini
"""
    fs.create_file(ini_path, contents=content)

    # ACT: Сохраняем ключ в новой, несуществующей секции 'Server'
    success = config.save_config_value("Server", "ip", "192.168.1.1", cfg_file=str(ini_path))
    assert success is True

    # ASSERT: Проверяем, что в файле появилась новая секция и ключ
    with open(ini_path) as f:
        file_content = f.read()

    assert "[Server]" in file_content
    assert "ip = 192.168.1.1" in file_content
