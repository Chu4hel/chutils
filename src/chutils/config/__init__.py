"""
Модуль для работы с конфигурацией.

Обеспечивает автоматический поиск файла `config.yml`, `config.yaml` или `config.ini`
в корне проекта и предоставляет удобные функции для чтения и сохранения настроек.
Поддерживает кастомные уровни логирования при условии, что модуль logger загружен.

### Переопределение конфигурации

Библиотека поддерживает многоуровневое переопределение настроек:
1. **Переменные окружения (`CH_[SECTION]_[KEY]`)**: Имеют наивысший приоритет.
2. **Локальный файл (`config.local.yml`)**: Переопределяет значения основного файла.
3. **Основной файл (`config.yml`)**: Базовые настройки проекта.

Локальные файлы конфигурации (например, `config.local.yml` или `config.local.ini`) должны
находиться в той же директории, что и основной файл. Это позволяет удобно управлять
чувствительными или специфичными для разработчика настройками, не коммитя их в репозиторий.
"""

import logging
import warnings
from typing import Any, Optional, TYPE_CHECKING, TypeVar, Tuple

from .core import get_config, aget_config, save_config_value, asave_config_value, _PROVIDERS
from .getters import (
    get_config_value,
    get_config_int,
    get_config_float,
    get_config_boolean,
    get_config_list,
    get_config_section,
    get_config_path
)
from .manager import _cm
from .utils import find_project_root, _check_pydantic
from .watcher import (
    on_config_change,
    start_config_watcher,
    stop_config_watcher,
)

if TYPE_CHECKING:
    from ..logger import ChutilsLogger
    from pydantic import BaseModel

# Тип для Pydantic моделей
T = TypeVar("T", bound="BaseModel")

# Настраиваем логгер для этого модуля.
logger = logging.getLogger(__name__)

# Экспортируем основные функции для внешнего использования
__all__ = [
    'get_config',
    'aget_config',
    'save_config_value',
    'asave_config_value',
    'get_config_value',
    'get_config_int',
    'get_config_float',
    'get_config_boolean',
    'get_config_list',
    'get_config_section',
    'get_config_path',
    'get_base_dir',
    'get_config_file_path',
    'is_config_loaded',
    'are_paths_initialized',
    'get_config_paths',
    'on_config_change',
    'start_config_watcher',
    'stop_config_watcher'
]


def _get_logger() -> 'ChutilsLogger':
    """
    Вспомогательная функция для получения типизированного логгера.

    Returns:
        Экземпляр логгера (может быть ChutilsLogger, если инициализирован).
    """
    return logger  # type: ignore


def __getattr__(name: str) -> Any:
    """
    Обеспечивает обратную совместимость для старых глобальных переменных.

    Согласно PEP 562, эта функция вызывается при обращении к отсутствующим атрибутам модуля.
    Мы используем её для перенаправления обращений к старым приватным переменным
    в новый менеджер состояния с выводом предупреждения об устаревании.
    """
    remap = {
        '_BASE_DIR': ('base_dir', 'get_base_dir()'),
        '_CONFIG_FILE_PATH': ('config_file_path', 'get_config_file_path()'),
        '_paths_initialized': ('paths_initialized', 'are_paths_initialized()'),
        '_config_object': ('config_object', 'get_config()'),
        '_config_loaded': ('config_loaded', 'is_config_loaded()'),
        '_get_config_paths': ('get_config_paths', 'get_config_paths()')
    }
    "Словарь соответствия: имя -> (атрибут в _cm, рекомендуемая публичная замена)"

    if name in remap:
        cm_attr, suggestion = remap[name]
        msg = f"Прямое обращение к 'chutils.config.{name}' устарело и будет удалено в будущих версиях."
        if suggestion:
            msg += f" Используйте {suggestion}."
        else:
            msg += " Используйте публичный API модуля."

        warnings.warn(msg, DeprecationWarning, stacklevel=2)

        # Если пути еще не инициализированы, инициализируем их при первом обращении
        if name in ['_BASE_DIR', '_CONFIG_FILE_PATH', '_get_config_paths'] and not _cm.paths_initialized:
            _cm.initialize_paths(find_project_root)

        return getattr(_cm, cm_attr)

    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


def _initialize_paths():
    """
    Внутренняя функция для инициализации путей (сохранена для обратной совместимости тестов).
    """
    _sync_legacy_state()
    _cm.initialize_paths(find_project_root)


def _sync_legacy_state():
    """
    Синхронизирует состояние и ОЧИЩАЕТ модуль от физических переменных,
    чтобы __getattr__ продолжал работать.
    """
    g = globals()
    mapping = {
        '_config_loaded': 'config_loaded',
        '_config_object': 'config_object',
        '_paths_initialized': 'paths_initialized',
        '_BASE_DIR': 'base_dir',
        '_CONFIG_FILE_PATH': 'config_file_path'
    }

    for mod_var, cm_attr in mapping.items():
        if mod_var in g:
            # Переносим значение в менеджер
            setattr(_cm, cm_attr, g[mod_var])
            # УДАЛЯЕМ из globals, чтобы __getattr__ снова мог перехватывать обращения
            del g[mod_var]


def get_base_dir() -> Optional[str]:
    """
    Возвращает абсолютный путь к корневой директории проекта.

    Если пути еще не инициализированы, запускает автоматический поиск.

    Returns:
        Путь к корню проекта или None, если корень не найден.
    """
    if not _cm.paths_initialized:
        _cm.initialize_paths(find_project_root)
    return _cm.base_dir


def get_config_file_path() -> Optional[str]:
    """
    Возвращает путь к основному файлу конфигурации, который используется в данный момент.

    Returns:
        Путь к файлу или None, если файл не найден.
    """
    if not _cm.paths_initialized:
        _cm.initialize_paths(find_project_root)
    return _cm.config_file_path


def is_config_loaded() -> bool:
    """
    Проверяет, была ли конфигурация уже загружена в память.

    Returns:
        True, если кэш конфигурации заполнен.
    """
    return _cm.config_loaded


def are_paths_initialized() -> bool:
    """
    Проверяет, были ли инициализированы пути к проекту и файлам конфигурации.

    Returns:
        True, если пути определены.
    """
    return _cm.paths_initialized


def get_config_paths(cfg_file: Optional[str] = None) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Возвращает пути к основному, специфичному для окружения и локальному файлам конфигурации.

    Args:
        cfg_file: Опциональный путь к основному файлу.

    Returns:
        Кортеж (путь_к_основному, путь_к_окружению, путь_к_локальному).
    """
    if not _cm.paths_initialized:
        _cm.initialize_paths(find_project_root)
    return _cm.get_config_paths(cfg_file)
