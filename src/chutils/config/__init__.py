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

import asyncio
import logging
import os
import time
import warnings
from pathlib import Path
from typing import Any, Optional, List, Dict, TYPE_CHECKING, TypeVar, Type, overload, Union, Tuple

from .manager import _cm
from .providers import get_providers
from .utils import find_project_root, _merge_configs, _nest_ini_dict, _get_typed_value
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
# Используем стандартный getLogger, чтобы избежать циклической рекурсии с logger.setup_logger.
# Если модуль logger уже загружен, logging вернет экземпляр ChutilsLogger.
logger = logging.getLogger(__name__)

# Реестр провайдеров (использует _nest_ini_dict из utils)
_PROVIDERS = get_providers(_nest_ini_dict)


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


def get_config_paths(cfg_file: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
    """
    Возвращает пути к основному и локальному файлам конфигурации.

    Args:
        cfg_file: Опциональный путь к основному файлу.

    Returns:
        Кортеж (путь_к_основному, путь_к_локальному).
    """
    if not _cm.paths_initialized:
        _cm.initialize_paths(find_project_root)
    return _cm.get_config_paths(cfg_file)


def _check_pydantic():
    """Проверяет наличие установленного пакета pydantic."""
    try:
        import pydantic
        return True
    except ImportError:
        return False


@overload
def get_config(model: Type[T]) -> T: ...


@overload
def get_config(model: None = None) -> Dict[str, Any]: ...


def get_config(model: Optional[Type[T]] = None) -> Union[Dict[str, Any], T]:
    """
    Загружает и объединяет конфигурацию из всех доступных источников.

    Результат кэшируется. Повторные вызовы возвращают кэшированный объект,
    если он не был сброшен (например, при сохранении нового значения).

    Args:
        model: Опциональный класс Pydantic модели для валидации.

    Returns:
       Словарь со всей конфигурацией проекта или экземпляр Pydantic модели.
       Если файлы не найдены, возвращается пустой словарь (или ошибка валидации модели).
    """
    # Поддержка старых тестов: синхронизируем состояние, если оно было изменено напрямую в модуле
    _sync_legacy_state()

    config_data = _cm.config_object

    if not (_cm.config_loaded and config_data is not None):
        # Гарантируем инициализацию путей
        if not _cm.paths_initialized:
            _cm.initialize_paths(find_project_root)

        main_path, local_path = _cm.get_config_paths()
        main_config: Dict = {}
        local_config: Dict = {}

        def load_from_path(path: str) -> Dict:
            ext = Path(path).suffix.lower()
            provider = _PROVIDERS.get(ext)
            if provider:
                data = provider.load(path)
                _get_logger().debug("Конфигурация загружена из %s (%s)", path, ext)
                return data
            _get_logger().warning("Неподдерживаемый формат файла конфигурации: %s", path)
            return {}

        if main_path and Path(main_path).exists():
            main_config = load_from_path(main_path)
        else:
            _get_logger().debug("Основной файл конфигурации не найден или не указан.")

        if local_path and Path(local_path).exists():
            local_config = load_from_path(local_path)
        else:
            _get_logger().debug("Локальный файл конфигурации не найден или не указан.")

        config_data = _merge_configs(main_config, local_config)
        _cm.config_object = config_data
        _cm.config_loaded = True

    if model is not None:
        if not _check_pydantic():
            raise ImportError(
                "Pydantic is required for configuration validation. "
                "Install it with 'pip install chutils[pydantic]' or 'poetry add pydantic'."
            )
        return model(**config_data)

    return config_data


@overload
async def aget_config(model: Type[T]) -> T: ...


@overload
async def aget_config(model: None = None) -> Dict[str, Any]: ...


async def aget_config(model: Optional[Type[T]] = None) -> Union[Dict[str, Any], T]:
    """
    Асинхронная версия get_config.

    Args:
        model: Опциональный класс Pydantic модели для валидации.

    Returns:
        Словарь конфигурации или экземпляр Pydantic модели.
    """
    return await asyncio.to_thread(get_config, model=model)


def save_config_value(
        section: str,
        key: str,
        value: Any,
        cfg_file: Optional[str] = None,
        save_to_local: bool = False,
        notify: bool = True
) -> bool:
    """
    Сохраняет или обновляет одно значение в файле конфигурации.

    Warning:
        Важно: При сохранении в `.yml` комментарии и форматирование будут утеряны.
        При сохранении в `.ini` - сохраняются.

    Args:
        section: Имя секции.
        key: Имя ключа в секции.
        value: Новое значение для ключа.
        cfg_file: Опциональный путь к файлу для сохранения. Если указан,
            имеет приоритет над `save_to_local`.
        save_to_local: Если True, и существует локальный файл конфигурации
            (например, `config.local.yml`), значение будет сохранено в него.
            По умолчанию False.
        notify: Если True (по умолчанию), Hot-Reload watcher уведомит о
            смене конфигурации. Если False, уведомление будет подавлено.

    Returns:
        True: Если значение было успешно обновлено и сохранено.
        False: Если файл не найден, или произошла ошибка.
    """
    # Поддержка старых тестов: синхронизируем состояние, если оно было изменено напрямую в модуле
    _sync_legacy_state()

    # Гарантируем инициализацию путей
    if not _cm.paths_initialized:
        _cm.initialize_paths(find_project_root)

    path: Optional[str] = None

    # Явный путь в cfg_file имеет высший приоритет
    if cfg_file:
        path = cfg_file
    else:
        main_path, local_path = _cm.get_config_paths()
        if save_to_local and local_path:
            path = local_path
            _get_logger().debug("Для сохранения выбран локальный файл конфигурации: %s", path)
        else:
            path = main_path

    if path is None:
        _get_logger().error("Невозможно сохранить значение: путь к файлу конфигурации не определен.")
        return False

    if not notify:
        # Фиксируем время внутреннего сохранения для подавления Hot-Reload
        _cm._last_internal_save_time = time.monotonic()

    ext = Path(path).suffix.lower()
    provider = _PROVIDERS.get(ext)

    if not provider:
        _get_logger().warning("Сохранение для формата %s не поддерживается.", ext)
        return False

    success = provider.save(path, section, key, value)
    if success:
        _get_logger().debug("Ключ '%s' в секции '[%s]' обновлен в файле %s", key, section, path)
        # Сбрасываем кэш
        _cm.config_object = None
        _cm.config_loaded = False
        return True

    return False


async def asave_config_value(
        section: str,
        key: str,
        value: Any,
        cfg_file: Optional[str] = None,
        save_to_local: bool = False,
        notify: bool = True
) -> bool:
    """
    Асинхронно сохраняет одно значение в конфигурационном файле.
    Работает как асинхронная обертка вокруг синхронной `save_config_value()`.

    Args:
        section: Имя секции.
        key: Имя ключа в секции.
        value: Новое значение для ключа.
        cfg_file: Опциональный путь к файлу для сохранения. Если указан,
            имеет приоритет над `save_to_local`.
        save_to_local: Если True, и существует локальный файл конфигурации
            (например, `config.local.yml`), значение будет сохранено в него.
            По умолчанию False.
        notify: Если True (по умолчанию), Hot-Reload watcher уведомит о
            смене конфигурации. Если False, уведомление будет подавлено.

    Returns:
        True: Если значение было успешно обновлено и сохранено.
        False: Если файл не найден, или произошла ошибка.
    """
    return await asyncio.to_thread(save_config_value, section, key, value, cfg_file, save_to_local, notify)


# --- Функции-обертки для удобного получения типизированных значений ---

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
    return _get_typed_value(section, key, int, fallback, get_config_value, config)


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
    return _get_typed_value(section, key, float, fallback, get_config_value, config)


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
        raise ValueError(f"Invalid boolean value: {v}")

    return _get_typed_value(section, key, bool_converter, fallback, get_config_value, config, type_name="bool")


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
        raise ValueError(f"Value is not a list: {v}")

    return _get_typed_value(section, key, list_converter, actual_fallback, get_config_value, config, type_name="list")


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
    """
    if config is None:
        config = get_config()

    section_data = config.get(section_name, fallback if fallback is not None else {})

    if model is not None:
        if not _check_pydantic():
            raise ImportError(
                "Pydantic is required for configuration validation. "
                "Install it with 'pip install chutils[pydantic]' or 'poetry add pydantic'."
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
                _get_logger().warning(
                    "Обнаружена попытка выхода за пределы корня проекта (Path Traversal). "
                    "Путь '%s' отклонен. Возвращено значение по умолчанию.", path_str
                )
                return fallback
            return str(resolved_path)
        except Exception as e:
            _get_logger().error("Ошибка при разрешении пути '%s': %s", path_str, e)
            return fallback

    return path_str
