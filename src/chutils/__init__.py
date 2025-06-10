"""
Пакет chutils - набор переиспользуемых утилит для Python.

Основная цель - упростить рутинные задачи, такие как работа с конфигурацией
и настройка логирования, с минимальными усилиями со стороны разработчика.

Ключевая особенность - автоматическое обнаружение корня проекта. Вам не нужно
вручную указывать пути к файлу 'config.ini' или папке 'logs'. Пакет сам найдет
их, ориентируясь на наличие 'config.ini' или 'pyproject.toml' в вашем проекте.

Основное использование (в 99% случаев):
-------------------------------------------
Вам не нужно ничего инициализировать. Просто импортируйте и используйте:

    from chutils.config import get_config_value
    from chutils.logger import setup_logger

    logger = setup_logger()
    db_host = get_config_value("Database", "host", "localhost")
    logger.info(f"Подключение к базе данных на {db_host}")

Ручная инициализация (для нестандартных случаев):
-------------------------------------------------
Если автоматика не сработала (например, у вас сложная структура проекта),
вы всегда можете указать путь к корню проекта вручную в самом начале
работы вашего приложения:

    import chutils
    chutils.init(base_dir="/path/to/your/project")

"""

import os

# Импортируем модули config и logger, чтобы их внутренние переменные
# были доступны для функции init.
from . import config
from . import logger

# --- Импорт публичных функций ---
# Мы явно импортируем только те функции, которые предназначены для
# конечного пользователя. Это формирует "чистый" публичный API пакета.

from .config import (
    load_config, save_config_value, get_config, get_config_value,
    get_config_int, get_config_float, get_config_boolean, get_config_list,
    get_multiple_config_values, get_config_section
)
from .logger import setup_logger


def init(base_dir: str):
    """
    Ручная инициализация пакета с указанием базовой директории проекта.

    Эту функцию нужно вызывать только в том случае, если автоматическое
    определение корня проекта не сработало. Вызывать следует один раз
    в самом начале работы основного скрипта вашего приложения.

    Args:
        base_dir (str): Абсолютный путь к корневой директории проекта,
                        где лежит 'config.ini'.

    Raises:
        ValueError: Если указанная директория не существует.
    """
    # Проверяем, что переданный путь является существующей директорией
    if not os.path.isdir(base_dir):
        raise ValueError(f"Указанная директория base_dir не существует или не является директорией: {base_dir}")

    # Вручную устанавливаем внутренние переменные в модуле config.
    # Это переопределит любые попытки автоматического поиска.
    config._BASE_DIR = base_dir
    config._CONFIG_FILE_PATH = os.path.join(base_dir, "config.ini")
    config._paths_initialized = True

    # Выводим сообщение, чтобы было понятно, что произошла ручная инициализация.
    print(f"Пакет chutils вручную инициализирован с базовой директорией: {base_dir}")


# --- Определение публичного API ---
# `__all__` — это специальный список, который определяет, какие имена будут
# импортированы, когда пользователь выполнит `from chutils import *`.
# Это также является явным соглашением о том, что является публичным API пакета.

__all__ = [
    # Основная функция ручной инициализации
    'init',

    # Функции из модуля config
    'load_config',
    'save_config_value',
    'get_config',
    'get_config_value',
    'get_config_int',
    'get_config_float',
    'get_config_boolean',
    'get_config_list',
    'get_multiple_config_values',
    'get_config_section',

    # Функции из модуля logger
    'setup_logger',
]
