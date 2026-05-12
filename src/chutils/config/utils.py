"""
Вспомогательные утилиты для работы с конфигурацией.
"""

import logging
from pathlib import Path
from typing import Any, Optional, List, Dict

# Настраиваем локальный логгер
logger = logging.getLogger(__name__)


def find_project_root(start_path: Path, markers: List[str]) -> Optional[Path]:
    """
    Ищет корень проекта, двигаясь вверх по дереву каталогов.

    Корень определяется по наличию одного из файлов-маркеров (например, .git или pyproject.toml).

    Args:
        start_path: Директория, с которой начинается поиск.
        markers: Список имен файлов или папок (маркеров), наличие которых
            в директории указывает на то, что это корень проекта.

    Returns:
        Объект Path, представляющий корневую директорию проекта, или None, если корень не найден.
    """
    current_path = start_path.resolve()
    # Идем вверх до тех пор, пока не достигнем корня файловой системы
    while current_path != current_path.parent:
        for marker in markers:
            if (current_path / marker).exists():
                logger.debug("Найден маркер '%s' в директории: %s", marker, current_path)
                return current_path
        current_path = current_path.parent
    logger.debug("Корень проекта не найден.")
    return None


def _merge_configs(main_config: Dict, local_config: Dict) -> Dict:
    """
    Рекурсивно объединяет два словаря конфигурации.

    Значения из `local_config` имеют приоритет и переопределяют значения из `main_config`.

    Args:
        main_config: Основной словарь конфигурации.
        local_config: Словарь с локальными переопределениями.

    Returns:
        Объединенный словарь конфигурации.
    """
    for key, value in local_config.items():
        if key in main_config and isinstance(main_config[key], dict) and isinstance(value, dict):
            main_config[key] = _merge_configs(main_config[key], value)
        else:
            main_config[key] = value
    return main_config


def _nest_ini_dict(flat_dict: Dict[str, Dict[str, Any]]) -> Dict:
    """
    Преобразует плоский словарь INI-секций во вложенную структуру.

    Разделяет имена секций по точкам (например, 'Logging.default' -> {'Logging': {'default': ...}}).

    Args:
        flat_dict: Словарь, где ключи - названия секций INI.

    Returns:
        Вложенный словарь.
    """
    nested_dict = {}
    for section_key, section_values in flat_dict.items():
        current_level = nested_dict
        parts = section_key.split('.')
        for i, part in enumerate(parts):
            if i == len(parts) - 1:  # Последняя часть - это название секции
                current_level[part] = section_values
            else:
                current_level = current_level.setdefault(part, {})
    return nested_dict


def _get_typed_value(
        section: str,
        key: str,
        converter: Any,
        fallback: Any,
        get_value_func: Any,
        config: Optional[Dict] = None,
        type_name: str = ""
) -> Any:
    """
    Внутренняя универсальная функция для получения типизированного значения.

    Используется для уменьшения дублирования кода в функциях get_config_*.

    Args:
        section: Имя секции.
        key: Имя ключа.
        converter: Функция-конвертер (например, int, float).
        fallback: Значение по умолчанию при отсутствии ключа или ошибке типа.
        get_value_func: Функция для получения сырого значения (get_config_value).
        config: Опциональный предварительно загруженный словарь конфигурации.
        type_name: Имя типа для информативного логирования.

    Returns:
        Типизированное значение или fallback.
    """
    value = get_value_func(section, key, fallback, config)
    if value == fallback:
        return fallback

    try:
        return converter(value)
    except (ValueError, TypeError):
        t_name = type_name or (converter.__name__ if hasattr(converter, '__name__') else str(converter))
        logger.warning(
            "Не удалось преобразовать значение '%s' для ключа '%s' в секции '[%s]' к типу %s. "
            "Возвращено значение по умолчанию: %s.",
            value, key, section, t_name, fallback
        )
        return fallback
