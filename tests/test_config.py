# -*- coding: utf-8 -*-
import pytest
from pathlib import Path
from chutils import config

# Используем константу для содержимого фейкового конфига, чтобы избежать дублирования.
FAKE_CONFIG_CONTENT = """
[Database]
host = localhost
port = 5432
enable_ssl = true
timeout = 15.5

[User]
name = Admin
roles =
    admin
    editor
    viewer

"""

@pytest.fixture
def config_fs(fs):  # fs - это фикстура из pyfakefs
    """
    Настраивает фейковую файловую систему для каждого теста.
    
    Эта фикстура выполняет три ключевые задачи:
    1. Сбрасывает состояние модуля `config` для изоляции тестов.
    2. Создает в памяти файловую структуру с `config.ini`.
    3. Устанавливает текущую рабочую директорию внутрь фейкового проекта.
    """
    # ARRANGE (Подготовка): Сбрасываем глобальные переменные в модуле config
    config._BASE_DIR = None
    config._CONFIG_FILE_PATH = None
    config._paths_initialized = False

    # ARRANGE: Определяем и создаем пути для фейкового проекта
    project_root = Path("/home/user/project")
    src_path = project_root / "src" / "app"
    fs.create_file(project_root / "config.ini", contents=FAKE_CONFIG_CONTENT)
    fs.create_dir(src_path)
    
    # ARRANGE: Переходим в рабочую директорию, откуда будет запущен поиск
    import os
    os.chdir(src_path)
    
    # Передаем управление тесту
    yield fs, project_root

    # CLEANUP (Очистка): Возвращаемся в корень после выполнения теста
    os.chdir("/")


def test_initialize_paths_success(config_fs):
    """Проверяет, что `_initialize_paths` находит корень проекта и путь к конфигу."""
    # ARRANGE: Получаем настроенную файловую систему и ожидаемый путь
    fs, project_root = config_fs
    
    # ACT: Вызываем тестируемую функцию
    config._initialize_paths()

    # ASSERT: Проверяем, что глобальные переменные модуля установились корректно
    # Сравниваем как объекты Path для независимости от ОС
    assert Path(config._BASE_DIR).as_posix().endswith('/home/user/project')
    assert Path(config._CONFIG_FILE_PATH).as_posix().endswith('/home/user/project/config.ini')

def test_get_config_path_raises_error_if_not_found(config_fs):
    """Проверяет, что `load_config` вызывает ошибку, если маркеры проекта не найдены."""
    # ARRANGE: Переходим в директорию, где нет маркеров проекта (`/`)
    import os
    os.chdir("/")
    # Сбрасываем состояние модуля, чтобы он заново запустил поиск
    config._paths_initialized = False

    # ACT & ASSERT: Проверяем, что вызов `load_config` приводит к FileNotFoundError
    with pytest.raises(FileNotFoundError):
        config.load_config()

def test_get_config_value(config_fs):
    """Тестирует чтение строкового значения и работу fallback."""
    # ACT: Читаем существующий ключ
    host = config.get_config_value("Database", "host")
    # ASSERT: Проверяем, что значение верное
    assert host == "localhost"
    
    # ACT: Читаем несуществующий ключ с указанием fallback
    non_existent = config.get_config_value("Database", "non_existent", fallback="default")
    # ASSERT: Проверяем, что вернулось fallback-значение
    assert non_existent == "default"

def test_get_config_typed_values(config_fs):
    """Тестирует чтение типизированных значений (int, float, bool)."""
    # ACT & ASSERT: Проверяем каждую функцию типизированного чтения
    assert config.get_config_int("Database", "port") == 5432
    assert config.get_config_float("Database", "timeout") == 15.5
    assert config.get_config_boolean("Database", "enable_ssl") is True

def test_get_config_list(config_fs):
    """Тестирует чтение многострочного значения как списка."""
    # ACT: Читаем ключ `roles`, значение которого занимает несколько строк
    roles = config.get_config_list("User", "roles")
    # ASSERT: Проверяем, что получили корректный список строк
    assert roles == ["admin", "editor", "viewer"]

def test_get_config_section(config_fs):
    """Тестирует получение целой секции [Database] как словаря."""
    # ACT: Запрашиваем всю секцию
    db_section = config.get_config_section("Database")
    # ASSERT: Проверяем, что словарь содержит все ключи и значения из секции
    assert db_section == {
        "host": "localhost",
        "port": "5432",
        "enable_ssl": "true",
        "timeout": "15.5"
    }

def test_save_config_value(config_fs):
    """Тестирует успешное сохранение нового значения в конфиг."""
    # ARRANGE: Получаем путь к фейковому конфигу
    path = config._get_config_path()
    
    # ACT: Сохраняем новое значение для хоста
    success = config.save_config_value("Database", "host", "new.host.com")
    
    # ASSERT: Проверяем, что функция отчиталась об успехе
    assert success is True

    # ASSERT: Читаем файл напрямую и проверяем, что содержимое изменилось как надо,
    # а остальные данные остались нетронутыми.
    with open(path, encoding='utf-8') as f:
        content = f.read()
    assert "host = new.host.com" in content
    assert "port = 5432" in content

def test_save_non_existent_key_fails(config_fs):
    """Проверяет, что функция `save_config_value` не создает новые ключи."""
    # ACT: Пытаемся сохранить значение для ключа, которого нет в секции
    success = config.save_config_value("Database", "non_existent_key", "some_value")
    
    # ASSERT: Проверяем, что функция вернула False, как и ожидалось
    assert success is False