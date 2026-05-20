"""
Функции доступа к значениям конфигурации.

Содержит типизированные обертки для удобного извлечения данных из 
загруженного объекта конфигурации.
"""

import logging
import os
from pathlib import Path
from typing import Any, Optional, List, Dict, TYPE_CHECKING, TypeVar, Type, overload, Union

from chutils.exceptions import ConfigParseError, OptionalDependencyError
from . import utils
from .core import get_config
from .manager import _cm

if TYPE_CHECKING:
    from pydantic import BaseModel

# Тип для Pydantic моделей
T = TypeVar("T", bound="BaseModel")

logger = logging.getLogger(__name__)


def get_config_value(section: str, key: str, fallback: Any = None, config: Optional[Dict] = None) -> Any:
    """
    Получает произвольное значение из конфигурации.

    Если значение не найдено или оно пустое, возвращает `fallback`.
    Для ключа `disable_keyring` в секции `secrets` проверяет переменную окружения.

    Также поддерживает универсальное переопределение через переменные окружения
    по шаблону `CH_[SECTION]_[KEY]`, если не установлено `CH_DISABLE_ENV_OVERRIDE=true`.

    Args:
        section: Имя секции.
        key: Имя ключа.
        fallback: Значение по умолчанию, если ключ не найден или его значение пустое.
        config: Опциональный, предварительно загруженный словарь конфигурации.

    Returns:
        Значение из конфигурации или `fallback`.
    """
    # 1. Проверка глобального флага отключения переопределения через ENV
    disable_env_override = os.getenv("CH_DISABLE_ENV_OVERRIDE", "").lower() in ("true", "1", "yes", "y")

    if not disable_env_override:
        # 2. Проверка универсального переопределения CH_[SECTION]_[KEY]
        # Используем верхний регистр для поиска в ENV согласно спецификации
        env_key = f"CH_{section.upper()}_{key.upper()}"
        env_value = os.getenv(env_key)
        if env_value is not None:
            return env_value

    # Проверка переменных окружения для специфических ключей (FR3: приоритет над конфигом)
    if section == "secrets" and key == "disable_keyring":
        env_val = os.getenv("CH_DISABLE_KEYRING_WARNING")
        if env_val is not None:
            return env_val

    if config is None:
        config = get_config()

    value = config.get(section, {}).get(key)

    # Если значение не найдено или является пустой строкой, возвращаем fallback
    if value is None or value == '':
        return fallback

    return value


def get_config_int(section: str, key: str, fallback: int = 0, config: Optional[Dict] = None) -> int:
    """
    Получает целочисленное значение из конфигурации.

    Args:
        section: Имя секции.
        key: Имя ключа.
        fallback: Значение по умолчанию, если ключ не найден или не может
            быть преобразован в int.
        config: Опциональный, предварительно загруженный словарь конфигурации.

    Returns:
        Целое число из конфигурации или `fallback`.
    """
    return utils._get_typed_value(section, key, int, fallback, get_config_value, config)


def get_config_float(section: str, key: str, fallback: float = 0.0, config: Optional[Dict] = None) -> float:
    """
    Получает дробное значение из конфигурации.

    Args:
        section: Имя секции.
        key: Имя ключа.
        fallback: Значение по умолчанию, если ключ не найден или не может
            быть преобразован в float.
        config: Опциональный, предварительно загруженный словарь конфигурации.

    Returns:
        Float или fallback.
    """
    return utils._get_typed_value(section, key, float, fallback, get_config_value, config)


def get_config_boolean(section: str, key: str, fallback: bool = False, config: Optional[Dict] = None) -> bool:
    """
    Получает булево значение из конфигурации.

    Распознает 'true', '1', 't', 'y', 'yes' как True и
    'false', '0', 'f', 'n', 'no' как False (без учета регистра).

    Args:
        section: Имя секции.
        key: Имя ключа.
        fallback: Значение по умолчанию, если ключ не найден или не может
            быть распознан как булево.
        config: Опциональный, предварительно загруженный словарь конфигурации.

    Returns:
        True или False.
    """

    def bool_converter(v: Any) -> bool:
        if isinstance(v, bool):
            return v
        s = str(v).lower()
        if s in ['true', '1', 't', 'y', 'yes']:
            return True
        if s in ['false', '0', 'f', 'n', 'no']:
            return False
        raise ConfigParseError(f"Invalid boolean value: {v}", section=section, key=key, value=v)

    return utils._get_typed_value(section, key, bool_converter, fallback, get_config_value, config, type_name="bool")


def get_config_list(
        section: str,
        key: str,
        fallback: Optional[List[Any]] = None,
        config: Optional[Dict] = None) -> List[Any]:
    """
    Получает значение как список из конфигурации.

    Args:
        section: Имя секции.
        key: Имя ключа.
        fallback: Значение по умолчанию, если ключ не найден.
        config: Опциональный, предварительно загруженный словарь конфигурации.

    Returns:
        Список из конфигурации или `fallback`. Если `fallback` не указан,
        возвращается пустой список.
    """
    actual_fallback = fallback if fallback is not None else []

    def list_converter(v: Any) -> List:
        if isinstance(v, list):
            return v
        raise ConfigParseError(f"Value is not a list: {v}", section=section, key=key, value=v)

    return utils._get_typed_value(section, key, list_converter, actual_fallback, get_config_value, config,
                                  type_name="list")


@overload
def get_config_section(
        section_name: str,
        fallback: Optional[Dict] = None,
        config: Optional[Dict] = None,
        model: None = None
) -> Dict[str, Any]: ...


@overload
def get_config_section(
        section_name: str,
        fallback: Optional[Dict] = None,
        config: Optional[Dict] = None,
        model: Type[T] = None
) -> T: ...


def get_config_section(
        section_name: str,
        fallback: Optional[Dict] = None,
        config: Optional[Dict] = None,
        model: Optional[Type[T]] = None
) -> Union[Dict[str, Any], T]:
    """
    Получает всю секцию конфигурации как словарь или Pydantic модель.

    Args:
        section_name: Имя секции.
        fallback: Значение по умолчанию, если секция не найдена.
        config: Опциональный, предварительно загруженный словарь конфигурации.
        model: Опциональный класс Pydantic модели для валидации секции.

    Returns:
        Словарь с содержимым секции или экземпляр Pydantic модели.
        Если `fallback` не указан и секция не найдена, возвращается пустой словарь.

    Raises:
        ConfigLoadError: Если произошла ошибка при чтении файлов конфигурации.
        ConfigParseError: Если файлы конфигурации содержат синтаксические ошибки.
        OptionalDependencyError: Если передана `model`, но пакет `pydantic` не установлен.
    """
    if config is None:
        config = get_config()

    section_data = config.get(section_name, fallback if fallback is not None else {})

    if model is not None:
        if not utils._check_pydantic():
            raise OptionalDependencyError(
                "Pydantic is required for configuration validation. "
                "Install it with 'pip install chutils[pydantic]' or 'poetry add pydantic'.",
                dependency="pydantic"
            )
        return model(**section_data)

    return section_data


def get_config_path(
        section: str,
        key: str,
        fallback: Optional[str] = None,
        config: Optional[Dict] = None,
        resolve_from_root: bool = True
) -> Optional[str]:
    """
    Получает путь из конфигурации.
    Функция автоматически добавляет _BASE_DIR к относительным путям,
    если resolve_from_root установлено в True.
    Args:
        section: Имя секции.
        key: Имя ключа.
        fallback: Значение по умолчанию, если ключ не найден.
        config: Опциональный, предварительно загруженный словарь конфигурации.
        resolve_from_root: Если True, относительные пути будут разрешаться
            относительно _BASE_DIR. Если False, пути возвращаются как есть,
            без добавления _BASE_DIR.
    Returns:
        Путь из конфигурации или `fallback`.
    """
    path_str = get_config_value(section, key, fallback, config)

    if not path_str:
        return fallback

    path_obj = Path(path_str)

    # Внутри модуля используем менеджер напрямую, чтобы не вызывать DeprecationWarning и избежать NameError
    base_dir = _cm.base_dir

    # Если путь относительный, _BASE_DIR определен и resolve_from_root включен, объединяем их
    if resolve_from_root and not path_obj.is_absolute() and base_dir:
        # Безопасное разрешение пути с проверкой на выход за пределы корня проекта (Path Traversal)
        try:
            base_dir_obj = Path(base_dir).resolve()
            resolved_path = (base_dir_obj / path_obj).resolve()

            # Проверяем, что итоговый путь находится внутри базовой директории
            if not str(resolved_path).startswith(str(base_dir_obj)):
                # Логируем через стандартный логгер, так как logger здесь доступен
                logger.warning(
                    "Обнаружена попытка выхода за пределы корня проекта (Path Traversal). "
                    "Путь '%s' отклонен. Возвращено значение по умолчанию.", path_str
                )
                return fallback
            return str(resolved_path)
        except Exception as e:
            logger.error("Ошибка при разрешении пути '%s': %s", path_str, e)
            return fallback

    return path_str
