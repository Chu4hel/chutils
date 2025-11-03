"""
Пакет chutils - набор переиспользуемых утилит для Python.

Основная цель - упростить рутинные задачи, такие как работа с конфигурацией,
логированием и управлением секретами, с минимальными усилиями со стороны разработчика.

Ключевые особенности:
- Автоматическое обнаружение корня проекта и файла конфигурации.
- Поддержка форматов `config.yml`, `config.yaml` и `config.ini` (YAML в приоритете).
- Удобные функции для доступа к настройкам.
- Готовый к работе логгер с выводом в консоль и ротируемые файлы.
- Безопасное хранение секретов через системное хранилище (keyring).

Основное использование:
----------------------
Вам не нужно ничего инициализировать. Просто импортируйте и используйте:

    from chutils import get_config_value, setup_logger, SecretManager

    logger = setup_logger()
    secrets = SecretManager("my_app")
    db_host = get_config_value("Database", "host", "localhost")
    logger.info(f"Подключение к базе данных на {db_host}")

Ручная инициализация (для нестандартных случаев):
-------------------------------------------------
Если автоматика не сработала, вы можете указать путь к корню проекта вручную:

    import chutils
    chutils.init(base_dir="/path/to/your/project")

"""

import os

from . import config
from . import logger

# --- Импорт публичных функций и классов ---
# Явно импортируем все, что должно быть доступно пользователю напрямую из пакета chutils.

from .config import (
    get_config,
    get_config_value,
    get_config_int,
    get_config_float,
    get_config_boolean,
    get_config_list,
    get_config_section
)
from .logger import setup_logger, ChutilsLogger, SafeTimedRotatingFileHandler
from .secret_manager import SecretManager
from .decorators import log_function_details


def init(base_dir: str):
    """
    Ручная инициализация пакета с указанием базовой директории проекта.

    Эту функцию нужно вызывать только в том случае, если автоматическое
    определение корня проекта не сработало. Вызывать следует один раз
    в самом начале работы основного скрипта вашего приложения.

    Args:
        base_dir (str): Абсолютный путь к корневой директории проекта.

    Raises:
        ValueError: Если указанная директория не существует.
    """
    if not os.path.isdir(base_dir):
        raise ValueError(f"Указанная директория base_dir не существует или не является директорией: {base_dir}")

    # Вручную устанавливаем базовую директорию. Модуль config сам найдет
    # нужный файл (yml или ini) при первом обращении.
    config._BASE_DIR = base_dir
    config._paths_initialized = True

    print(f"Пакет chutils вручную инициализирован с базовой директорией: {base_dir}")


# --- Определение публичного API (`__all__`) ---
# Определяет, что будет импортировано при `from chutils import *`

__all__ = [
    # Основная функция ручной инициализации
    'init',

    # Функции и классы из модуля config
    'get_config',
    'get_config_value',
    'get_config_int',
    'get_config_float',
    'get_config_boolean',
    'get_config_list',
    'get_config_section',

    # Функции и классы из модуля logger
    'setup_logger',
    'ChutilsLogger',
    'SafeTimedRotatingFileHandler',

    # Классы из модуля secret_manager
    'SecretManager',

    # Декораторы
    'log_function_details',
]
