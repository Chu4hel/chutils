# -*- coding: utf-8 -*-
import logging
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


def test_get_config_int_logs_warning_on_failure(config_fs, caplog):
    """
    Проверяет, что get_config_int логирует предупреждение при ошибке преобразования.
    """
    fs, project_root = config_fs
    content = """
Database:
  port: "not-an-int"
"""
    fs.create_file(project_root / "config.yml", contents=content)

    # ACT
    with caplog.at_level(logging.WARNING):
        result = config.get_config_int("Database", "port", fallback=999)

    # ASSERT
    assert result == 999
    assert len(caplog.records) == 1
    assert caplog.records[0].levelno == logging.WARNING
    assert "Не удалось преобразовать" in caplog.text
    assert "'not-an-int'" in caplog.text
    assert "к типу int" in caplog.text


def test_get_config_float_logs_warning_on_failure(config_fs, caplog):
    """
    Проверяет, что get_config_float логирует предупреждение при ошибке преобразования.
    """
    fs, project_root = config_fs
    content = """
Database:
  timeout: "not-a-float"
"""
    fs.create_file(project_root / "config.yml", contents=content)

    # ACT
    with caplog.at_level(logging.WARNING):
        result = config.get_config_float("Database", "timeout", fallback=99.9)

    # ASSERT
    assert result == 99.9
    assert len(caplog.records) == 1
    assert caplog.records[0].levelno == logging.WARNING
    assert "Не удалось преобразовать" in caplog.text
    assert "'not-a-float'" in caplog.text
    assert "к типу float" in caplog.text

def test_get_config_returns_empty_dict_when_no_file_found(config_fs, caplog):
    """
    Проверяет, что get_config() возвращает пустой словарь и не падает,
    если файл конфигурации не найден.
    """
    fs, project_root = config_fs
    # Создаем только маркер проекта, но не сам файл конфигурации
    fs.create_file(project_root / "pyproject.toml")
    import os
    os.chdir(project_root)  # Убедимся, что мы в корне проекта

    # ACT
    with caplog.at_level(logging.DEBUG):
        result = config.get_config()

    # ASSERT
    assert result == {}
    # Проверяем, что было записано отладочное сообщение, а не ошибка
    assert "Основной файл конфигурации не найден или не указан" in caplog.text
    assert "Локальный файл конфигурации не найден или не указан" in caplog.text
    # Убедимся, что нет сообщений об ошибках уровня ERROR или CRITICAL
    for record in caplog.records:
        assert record.levelno < logging.ERROR


def test_local_config_overrides_main_yaml(config_fs):
    """
    Проверяет, что config.local.yml переопределяет значения из config.yml.
    """
    fs, project_root = config_fs
    main_yaml_content = """
App:
  name: MainApp
  version: 1.0
  settings:
    debug: false
    log_level: INFO
Database:
  host: localhost
  port: 5432
"""
    local_yaml_content = """
App:
  version: 1.1
  settings:
    debug: true
Database:
  port: 6000
  user: local_user
"""
    fs.create_file(project_root / "config.yml", contents=main_yaml_content)
    fs.create_file(project_root / "config.local.yml", contents=local_yaml_content)
    fs.create_file(project_root / "pyproject.toml", contents="") # Маркер проекта

    # Сбрасываем кэш конфигурации
    config._config_loaded = False
    config._config_object = None
    config._paths_initialized = False

    # ACT
    cfg = config.get_config()

    # ASSERT
    assert cfg["App"]["name"] == "MainApp"  # Не переопределено
    assert cfg["App"]["version"] == 1.1     # Переопределено
    assert cfg["App"]["settings"]["debug"] is True # Вложенное переопределение
    assert cfg["App"]["settings"]["log_level"] == "INFO" # Не переопределено
    assert cfg["Database"]["host"] == "localhost" # Не переопределено
    assert cfg["Database"]["port"] == 6000     # Переопределено
    assert cfg["Database"]["user"] == "local_user" # Добавлено новое значение


def test_only_local_config_exists(config_fs):
    """
    Проверяет, что если существует только config.local.yml, он загружается корректно.
    """
    fs, project_root = config_fs
    local_yaml_content = """
App:
  name: LocalApp
  version: 2.0
"""
    fs.create_file(project_root / "config.local.yml", contents=local_yaml_content)
    fs.create_file(project_root / "pyproject.toml", contents="") # Маркер проекта

    # Сбрасываем кэш конфигурации
    config._config_loaded = False
    config._config_object = None
    config._paths_initialized = False

    # ACT
    cfg = config.get_config()

    # ASSERT
    assert cfg["App"]["name"] == "LocalApp"
    assert cfg["App"]["version"] == 2.0
    assert "Database" not in cfg # Убедимся, что нет секций из несуществующего основного файла


def test_save_config_value_does_not_affect_local_config(config_fs):
    """
    Проверяет, что save_config_value изменяет только основной config.yml,
    не затрагивая config.local.yml.
    """
    fs, project_root = config_fs
    main_yaml_content = """
App:
  name: MainApp
  version: 1.0
"""
    local_yaml_content = """
App:
  version: 1.1
  settings:
    debug: true
"""
    main_config_path = project_root / "config.yml"
    local_config_path = project_root / "config.local.yml"

    fs.create_file(main_config_path, contents=main_yaml_content)
    fs.create_file(local_config_path, contents=local_yaml_content)
    fs.create_file(project_root / "pyproject.toml", contents="") # Маркер проекта

    # Сбрасываем кэш конфигурации
    config._config_loaded = False
    config._config_object = None
    config._paths_initialized = False

    # ACT: Сохраняем значение в основной конфиг
    success = config.save_config_value("App", "version", 1.2)
    assert success is True

    # ASSERT: Проверяем, что основной конфиг изменился
    import yaml
    with open(main_config_path) as f:
        main_data_after_save = yaml.safe_load(f)
    assert main_data_after_save["App"]["version"] == 1.2

    # ASSERT: Проверяем, что локальный конфиг остался без изменений
    with open(local_config_path) as f:
        local_data_after_save = yaml.safe_load(f)
    assert local_data_after_save["App"]["version"] == 1.1
    assert local_data_after_save["App"]["settings"]["debug"] is True

    # ASSERT: Проверяем, что get_config() возвращает объединенные данные с учетом изменений
    config._config_loaded = False # Сбрасываем кэш для get_config
    merged_cfg = config.get_config()
    assert merged_cfg["App"]["name"] == "MainApp"
    assert merged_cfg["App"]["version"] == 1.1 # Локальный конфиг переопределяет основной
    assert merged_cfg["App"]["settings"]["debug"] is True


def test_local_config_overrides_main_ini(config_fs):
    """
    Проверяет, что config.local.ini переопределяет значения из config.ini.
    """
    fs, project_root = config_fs
    main_ini_content = """
[App]
name = MainApp
version = 1.0

[Database]
host = localhost
port = 5432
"""
    local_ini_content = """
[App]
version = 1.1

[Database]
port = 6000
user = local_user
"""
    fs.create_file(project_root / "config.ini", contents=main_ini_content)
    fs.create_file(project_root / "config.local.ini", contents=local_ini_content)
    fs.create_file(project_root / "pyproject.toml", contents="") # Маркер проекта

    # Сбрасываем кэш конфигурации
    config._config_loaded = False
    config._config_object = None
    config._paths_initialized = False

    # ACT
    cfg = config.get_config()

    # ASSERT
    assert cfg["App"]["name"] == "MainApp"
    assert cfg["App"]["version"] == "1.1"
    assert cfg["Database"]["host"] == "localhost"
    assert cfg["Database"]["port"] == "6000" # INI парсит все как строки
    assert cfg["Database"]["user"] == "local_user"

