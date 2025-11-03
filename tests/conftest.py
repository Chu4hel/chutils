from pathlib import Path

import pytest


@pytest.fixture
def config_fs(fs):  # fs - это фикстура из pyfakefs
    from chutils import config
    """
    Настраивает фейковую файловую систему и сбрасывает состояние модуля config.
    """
    # Сброс состояния модуля
    config._BASE_DIR = None
    config._CONFIG_FILE_PATH = None
    config._paths_initialized = False
    config._config_object = None
    config._config_loaded = False

    # Создание файловой структуры
    project_root = Path("/home/user/project")
    src_path = project_root / "src" / "app"
    fs.create_dir(src_path)

    # Установка текущей директории
    import os
    os.chdir(src_path)

    # Передаем управление тесту
    yield fs, project_root

    # Очистка
    os.chdir("/")
