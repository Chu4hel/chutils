"""
Функции доступа к значениям конфигурации.

Содержит типизированные обертки для удобного извлечения данных из
загруженного объекта конфигурации.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, TYPE_CHECKING, TypeVar, overload, cast

from chutils.exceptions import ConfigParseError, OptionalDependencyError
from chutils.typing import JSONDict
from . import utils
from .core import get_config
from .manager import _cm

if TYPE_CHECKING:
    from pydantic import BaseModel

# Тип для Pydantic моделей
T = TypeVar("T", bound="BaseModel")

logger = logging.getLogger(__name__)


def get_config_value(
        section: str,
        key: str,
        fallback: Any = None,
        config: JSONDict | None = None,
        required: bool = False,
) -> Any:
    """
    Получает произвольное значение из конфигурации.

    Если значение не найдено или оно пустое, возвращает `fallback`.
    Поддерживает универсальное переопределение через переменные окружения
    по шаблону `CH_[SECTION]_[KEY]`, если не установлено `CH_DISABLE_ENV_OVERRIDE=true`.

    Args:
        section: Имя секции.
        key: Имя ключа.
        fallback: Значение по умолчанию, если ключ не найден или его значение пустое.
        config: Опциональный, предварительно загруженный словарь конфигурации.
        required: Если True, выбросит ConfigKeyNotFoundError при отсутствии ключа или пустом значении.

    Returns:
        Значение из конфигурации или `fallback`.
    """
    if config is None:
        config = cast(JSONDict, get_config())

    section_data = config.get(section)
    if section_data is None:
        for k, v in config.items():
            if k.lower() == section.lower():
                section_data = v
                break
        else:
            section_data = {}

    if not isinstance(section_data, dict):
        if required:
            from chutils.exceptions import ConfigKeyNotFoundError

            raise ConfigKeyNotFoundError(
                f"Section '{section}' not found in configuration"
            )
        return fallback

    value = section_data.get(key)
    if value is None:
        for k, v in section_data.items():
            if k.lower() == key.lower():
                value = v
                break

    # Если значение не найдено или является пустой строкой, возвращаем fallback
    if value is None or value == "":
        if required:
            from chutils.exceptions import ConfigKeyNotFoundError

            raise ConfigKeyNotFoundError(
                f"Key '{key}' not found in section '{section}' of configuration"
            )
        return fallback

    return value


def get_config_int(
        section: str,
        key: str,
        fallback: int = 0,
        config: JSONDict | None = None,
        required: bool = False,
) -> int:
    """
    Получает целочисленное значение из конфигурации.

    Args:
        section: Имя секции.
        key: Имя ключа.
        fallback: Значение по умолчанию, если ключ не найден или не может
            быть преобразован в int.
        config: Опциональный, предварительно загруженный словарь конфигурации.
        required: Если True, выбросит ConfigKeyNotFoundError при отсутствии ключа.

    Returns:
        Целое число из конфигурации или `fallback`.
    """
    return cast(
        int,
        utils._get_typed_value(
            section, key, int, fallback, get_config_value, config, required=required
        ),
    )


def get_config_float(
        section: str,
        key: str,
        fallback: float = 0.0,
        config: JSONDict | None = None,
        required: bool = False,
) -> float:
    """
    Получает дробное значение из конфигурации.

    Args:
        section: Имя секции.
        key: Имя ключа.
        fallback: Значение по умолчанию, если ключ не найден или не может
            быть преобразован в float.
        config: Опциональный, предварительно загруженный словарь конфигурации.
        required: Если True, выбросит ConfigKeyNotFoundError при отсутствии ключа.

    Returns:
        Float или fallback.
    """
    return cast(
        float,
        utils._get_typed_value(
            section, key, float, fallback, get_config_value, config, required=required
        ),
    )


def get_config_boolean(
        section: str,
        key: str,
        fallback: bool = False,
        config: JSONDict | None = None,
        required: bool = False,
) -> bool:
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
        required: Если True, выбросит ConfigKeyNotFoundError при отсутствии ключа.

    Returns:
        True или False.
    """

    def bool_converter(v: Any) -> bool:
        if isinstance(v, bool):
            return v
        s = str(v).lower()
        if s in ["true", "1", "t", "y", "yes"]:
            return True
        if s in ["false", "0", "f", "n", "no"]:
            return False
        raise ConfigParseError(
            f"Неверное булево значение для ключа '{key}': {v}",
            hint="Допустимые значения: true/false, yes/no, 1/0, t/f.",
            section=section,
            key=key,
            value=v,
        )

    return cast(
        bool,
        utils._get_typed_value(
            section,
            key,
            bool_converter,
            fallback,
            get_config_value,
            config,
            type_name="bool",
            required=required,
        ),
    )


def get_config_list(
        section: str,
        key: str,
        fallback: list[Any] | None = None,
        config: JSONDict | None = None,
        required: bool = False,
) -> list[Any]:
    """
    Получает значение как список из конфигурации.

    Args:
        section: Имя секции.
        key: Имя ключа.
        fallback: Значение по умолчанию, если ключ не найден.
        config: Опциональный, предварительно загруженный словарь конфигурации.
        required: Если True, выбросит ConfigKeyNotFoundError при отсутствии ключа.

    Returns:
        Список из конфигурации или `fallback`. Если `fallback` не указан,
        возвращается пустой список.
    """
    actual_fallback = fallback if fallback is not None else []

    def list_converter(v: Any) -> list[Any]:
        if isinstance(v, list):
            return v
        raise ConfigParseError(
            f"Значение для '{key}' не является списком: {v}",
            hint="Убедитесь, что в конфигурации это поле представлено в виде списка (YAML: - item).",
            section=section,
            key=key,
            value=v,
        )

    return cast(
        list[Any],
        utils._get_typed_value(
            section,
            key,
            list_converter,
            actual_fallback,
            get_config_value,
            config,
            type_name="list",
            required=required,
        ),
    )


@overload
def get_config_section(
        section_name: str,
        fallback: JSONDict | None = None,
        config: JSONDict | None = None,
        model: None = None,
        required: bool = False,
) -> JSONDict: ...


@overload
def get_config_section(
        section_name: str,
        fallback: JSONDict | None = None,
        config: JSONDict | None = None,
        model: type[T] = ...,
        required: bool = False,
) -> T: ...


def get_config_section(
        section_name: str,
        fallback: JSONDict | None = None,
        config: JSONDict | None = None,
        model: type[T] | None = None,
        required: bool = False,
) -> JSONDict | T:
    """
    Получает всю секцию конфигурации как словарь или Pydantic модель.

    Args:
        section_name: Имя секции.
        fallback: Значение по умолчанию, если секция не найдена.
        config: Опциональный, предварительно загруженный словарь конфигурации.
        model: Опциональный класс Pydantic модели для валидации секции.
        required: Если True, выбросит ConfigKeyNotFoundError при отсутствии секции.

    Returns:
        Словарь с содержимым секции или экземпляр Pydantic модели.
        Если `fallback` не указан и секция не найдена, возвращается пустой словарь.

    Raises:
        ConfigLoadError: Если произошла ошибка при чтении файлов конфигурации.
        ConfigParseError: Если файлы конфигурации содержат синтаксические ошибки.
        OptionalDependencyError: Если передана `model`, но пакет `pydantic` не установлен.
        ConfigKeyNotFoundError: Если секция не найдена и required=True.
    """
    if config is None:
        config = cast(JSONDict, get_config())

    section_data = config.get(section_name)
    if section_data is None:
        # Case-insensitive fallback
        for k, v in config.items():
            if k.lower() == section_name.lower():
                section_data = v
                break
        else:
            if required:
                from chutils.exceptions import ConfigKeyNotFoundError

                raise ConfigKeyNotFoundError(
                    f"Section '{section_name}' not found in configuration"
                )
            section_data = fallback if fallback is not None else {}

    if model is not None:
        from chutils.env import has_pydantic

        if not has_pydantic():
            raise OptionalDependencyError(
                "Pydantic is required for configuration validation.",
                dependency="pydantic",
                hint="Install it with 'pip install chutils[pydantic]' or 'poetry add pydantic'.",
            )
        return model(**(cast(dict[str, Any], section_data)))

    return cast(JSONDict, section_data)


def get_config_path(
        section: str,
        key: str,
        fallback: str | None = None,
        config: JSONDict | None = None,
        resolve_from_root: bool = True,
        required: bool = False,
) -> str | None:
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
        required: Если True, выбросит ConfigKeyNotFoundError при отсутствии ключа.
    Returns:
        Путь из конфигурации или `fallback`.
    """
    path_str = cast(
        str | None,
        get_config_value(section, key, fallback, config, required=required),
    )

    if not path_str:
        return fallback

    Path(path_str)

    # Внутри модуля используем менеджер напрямую, чтобы не вызывать DeprecationWarning и избежать NameError
    base_dir = _cm.base_dir

    # Если base_dir определен и resolve_from_root включен, безопасно разрешаем путь
    if resolve_from_root and base_dir:
        # Безопасное разрешение пути с проверкой на выход за пределы корня проекта (Path Traversal)
        try:
            from chutils.fs import resolve_safe_path
            from chutils.exceptions import PathTraversalError

            return str(resolve_safe_path(path_str, base_dir))
        except PathTraversalError as e:
            # Пробрасываем исключение безопасности выше для перехвата в CLI
            raise e
        except Exception as e:
            logger.error("Ошибка при разрешении пути '%s': %s", path_str, e)
            return fallback

    return path_str


def validate_required_keys(
        section: str,
        keys: list[str],
        config: JSONDict | None = None,
) -> None:
    """
    Проверяет наличие списка обязательных ключей в указанной секции конфигурации.
    Служит для групповой валидации за один проход. Выбрасывает ConfigValidationGroupError,
    если один или несколько ключей отсутствуют или пусты.

    Args:
        section: Имя секции для валидации.
        keys: Список ключей, которые должны присутствовать и быть не пустыми.
        config: Опциональный, предварительно загруженный словарь конфигурации.

    Raises:
        ConfigValidationGroupError: Если один или несколько ключей отсутствуют.
    """
    if config is None:
        config = cast(JSONDict, get_config())

    errors: list[Exception] = []

    for key in keys:
        try:
            get_config_value(section, key, config=config, required=True)
        except Exception as e:
            errors.append(e)

    if errors:
        from chutils.exceptions import ConfigValidationGroupError

        raise ConfigValidationGroupError(
            f"Validation failed for section '{section}'. Missing or empty required keys.",
            exceptions=errors,
        )
