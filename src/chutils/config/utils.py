"""
Вспомогательные утилиты для работы с конфигурацией.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from collections.abc import Callable

from chutils.typing import JSONDict
from .providers import get_providers

# Настраиваем локальный логгер
logger = logging.getLogger(__name__)


def find_project_root(start_path: Path, markers: list[str]) -> Path | None:
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


def deep_merge(dict1: JSONDict, dict2: JSONDict) -> JSONDict:
    """
    Рекурсивно объединяет два словаря.

    Значения из `dict2` имеют приоритет и переопределяют значения из `dict1`.
    Изменяет `dict1` на месте.

    Args:
        dict1: Базовый словарь.
        dict2: Словарь с переопределениями.

    Returns:
        Объединенный словарь.
    """
    for key, value in dict2.items():
        if key in dict1 and isinstance(dict1[key], dict) and isinstance(value, dict):
            dict1[key] = deep_merge(dict1[key], value)
        else:
            dict1[key] = value
    return dict1


def _nest_ini_dict(flat_dict: dict[str, dict[str, Any]]) -> JSONDict:
    """
    Преобразует плоский словарь INI-секций во вложенную структуру.

    Разделяет имена секций по точкам (например, 'Logging.default' -> {'Logging': {'default': ...}}).

    Args:
        flat_dict: Словарь, где ключи - названия секций INI.

    Returns:
        Вложенный словарь.
    """
    nested_dict: JSONDict = {}
    for section_key, section_values in flat_dict.items():
        current_level = nested_dict
        parts = section_key.split('.')
        for i, part in enumerate(parts):
            if i == len(parts) - 1:  # Последняя часть - это название секции
                current_level[part] = section_values
            else:
                # В INI значения всегда словари, поэтому current_level[part] тоже будет словарем
                if part not in current_level:
                    current_level[part] = {}
                current_level = current_level[part]
    return nested_dict


def _check_pydantic() -> bool:
    """Проверяет наличие установленного пакета pydantic."""
    try:
        import pydantic  # noqa: F401
        return True
    except ImportError:
        return False


# Реестр провайдеров (использует _nest_ini_dict из этого же модуля)
_PROVIDERS = get_providers(_nest_ini_dict)


def _get_typed_value(
        section: str,
        key: str,
        converter: Callable[[Any], Any],
        fallback: Any,
        get_value_func: Callable[..., Any],
        config: JSONDict | None = None,
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


def load_pyproject_toml(path: str) -> JSONDict:
    """
    Загружает и парсит секцию [tool.chutils.ai-lint] из pyproject.toml.

    Использует tomllib (Python >= 3.11) или tomli, если доступны.
    В качестве fallback использует простой строковый парсер для избежания
    зависимостей на старых версиях Python.
    """
    try:
        # Пробуем стандартный tomllib (Python 3.11+)
        import tomllib
        with open(path, "rb") as f:
            data = tomllib.load(f)
            tool_dict = data.get("tool", {})
            if isinstance(tool_dict, dict):
                chutils_dict = tool_dict.get("chutils", {})
                if isinstance(chutils_dict, dict):
                    ai_lint_dict = chutils_dict.get("ai-lint", {})
                    if isinstance(ai_lint_dict, dict):
                        return ai_lint_dict
            return {}
    except ImportError:
        try:
            # Пробуем tomli
            import tomli
            with open(path, "rb") as f:
                data = tomli.load(f)
                tool_dict = data.get("tool", {})
                if isinstance(tool_dict, dict):
                    chutils_dict = tool_dict.get("chutils", {})
                    if isinstance(chutils_dict, dict):
                        ai_lint_dict = chutils_dict.get("ai-lint", {})
                        if isinstance(ai_lint_dict, dict):
                            return ai_lint_dict
                return {}
        except ImportError:
            # Ручной легковесный fallback парсер
            return _parse_pyproject_toml_fallback(path)


def _parse_pyproject_toml_fallback(path: str) -> JSONDict:
    """
    Ручной парсер для извлечения секции [tool.chutils.ai-lint] из TOML.
    """
    import ast

    result: JSONDict = {}
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()
    except Exception:
        return result

    in_section = False
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        if line.startswith("["):
            # Проверяем, наша ли это секция
            section_name = line.strip("[]").strip()
            if section_name == "tool.chutils.ai-lint":
                in_section = True
            else:
                in_section = False
            continue

        if in_section:
            if "=" in line:
                key, val_str = line.split("=", 1)
                key = key.strip()
                val_str = val_str.strip()

                # Парсим базовые типы (bool, int, float, list, str)
                try:
                    val = ast.literal_eval(val_str)
                    result[key] = val
                except Exception:
                    if val_str.lower() == "true":
                        result[key] = True
                    elif val_str.lower() == "false":
                        result[key] = False
                    elif val_str.startswith("[") and val_str.endswith("]"):
                        items = [item.strip(" '\"") for item in val_str[1:-1].split(",") if item.strip()]
                        result[key] = items
                    elif (val_str.startswith('"') and val_str.endswith('"')) or (
                            val_str.startswith("'") and val_str.endswith("'")):
                        result[key] = val_str[1:-1]
                    else:
                        result[key] = val_str

    return result
