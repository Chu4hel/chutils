import concurrent.futures
import os
from concurrent.futures.process import ProcessPoolExecutor as _ProcessPoolExecutor
from concurrent.futures.thread import ThreadPoolExecutor as _ThreadPoolExecutor

# Предотвращаем маршрутизацию локального трафика через внешние прокси в тестах
os.environ.setdefault("NO_PROXY", "127.0.0.1,localhost")

import keyring
import pytest

# Патч совместимости для Python 3.15 (PEP 690 lazy_import proxy в standard library concurrent.futures)
if getattr(concurrent.futures, "ThreadPoolExecutor", None) is not _ThreadPoolExecutor:
    concurrent.futures.ThreadPoolExecutor = _ThreadPoolExecutor  # type: ignore[misc]
if getattr(concurrent.futures, "ProcessPoolExecutor", None) is not _ProcessPoolExecutor:
    concurrent.futures.ProcessPoolExecutor = _ProcessPoolExecutor  # type: ignore[misc]


pytest_plugins = ["chutils.testing.fixtures"]

try:
    keyring.get_keyring()
except Exception:
    pass


@pytest.fixture
def config_fs(fs):  # fs - это фикстура из pyfakefs
    import os
    import shutil
    from pathlib import Path

    from chutils import config
    from chutils.logger import core as logger_core
    from chutils.logger.internal import utils as logger_utils

    """
    Настраивает фейковую файловую систему и сбрасывает состояние модулей config и logger.
    """
    original_cwd = os.getcwd()

    # Сброс состояния модуля config через менеджер
    config._cm._reset()

    # Сброс состояния модуля logger
    logger_core._file_handler_cache.clear()
    logger_core._initialization_message_shown = False
    logger_utils._LOG_DIR = None
    logger_utils._async_listeners.clear()

    # Создание файловой структуры
    project_root = Path("/home/user/project")
    src_path = project_root / "src" / "app"
    fs.create_dir(src_path)

    # Установка текущей директории
    os.chdir(src_path)

    # Передаем управление тесту
    yield fs, project_root

    # Сброс состояния модулей
    config._cm._reset()
    logger_core._file_handler_cache.clear()
    logger_core._initialization_message_shown = False
    logger_utils._LOG_DIR = None
    logger_utils._async_listeners.clear()

    # Восстановление исходной рабочей директории
    try:
        os.chdir(original_cwd)
    except Exception:
        pass

    # Гарантированная очистка реальной папки на диске (если pyfakefs пропустил вызов на Windows)
    try:
        with fs.pause():
            real_home = (
                Path("C:/home") if os.name == "nt" else Path("/home/user/project")
            )
            if real_home.exists():
                shutil.rmtree(real_home, ignore_errors=True)
    except Exception:
        pass


@pytest.fixture(autouse=True, scope="session")
def cleanup_leaked_real_dirs_session():
    """Гарантирует удаление временных директорий на реальном диске после всей сессии pytest."""
    yield
    import os
    import shutil
    from pathlib import Path

    if os.name == "nt":
        real_home = Path("C:/home")
        if real_home.exists():
            shutil.rmtree(real_home, ignore_errors=True)


@pytest.fixture
def project_with_marker(config_fs):
    """
    Фикстура, которая подготавливает фейковую ФС с маркером проекта.
    Это необходимо для тестов, которые зависят от автообнаружения корня проекта.
    """
    fs, project_root = config_fs
    fs.create_file(project_root / "pyproject.toml")
    return fs, project_root
