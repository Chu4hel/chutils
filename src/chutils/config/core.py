"""
Ядро системы конфигурации.

Обеспечивает оркестрацию загрузки из разных источников (основной файл, 
специфичный для окружения, локальный, переменные окружения) и сохранение значений.
"""

import asyncio
import logging
from pathlib import Path
from typing import Any, Optional, Dict, TYPE_CHECKING, TypeVar, Type, Union

from chutils.exceptions import OptionalDependencyError
from .manager import _cm
from .providers import get_providers
from . import utils

if TYPE_CHECKING:
    from pydantic import BaseModel

# Тип для Pydantic моделей
T = TypeVar("T", bound="BaseModel")

logger = logging.getLogger(__name__)

# Реестр провайдеров (использует _nest_ini_dict из utils)
_PROVIDERS = get_providers(utils._nest_ini_dict)


def get_config(model: Optional[Type[T]] = None) -> Union[Dict[str, Any], T]:
    """
    Загружает и объединяет конфигурацию из всех доступных источников.

    Результат кэшируется. Повторные вызовы возвращают кэшированный объект,
    если он не был сброшен (например, при сохранении нового значения).

    Порядок применения конфигураций (от меньшего приоритета к большему):
    1. Основной файл (config.yml)
    2. Файл окружения (config.{CH_ENV}.yml)
    3. Локальный файл (config.local.yml)
    4. Переменные окружения (CH_SECTION_KEY)

    Args:
        model: Опциональный класс Pydantic модели для валидации.

    Returns:
       Словарь со всей конфигурацией проекта или экземпляр Pydantic модели.
       Если файлы не найдены, возвращается пустой словарь (или ошибка валидации модели).

    Raises:
        ConfigLoadError: Если произошла ошибка при чтении файлов конфигурации.
        ConfigParseError: Если файлы конфигурации содержат синтаксические ошибки.
        OptionalDependencyError: Если передана `model`, но пакет `pydantic` не установлен.
    """

    def _do_load():
        # Гарантируем инициализацию путей
        if not _cm.paths_initialized:
            _cm.initialize_paths(utils.find_project_root)

        _cm.acquire_file_lock()
        try:
            main_path, env_path, local_path = _cm.get_config_paths()
            config_data: Dict = {}

            def load_from_path(path: str) -> Dict:
                ext = Path(path).suffix.lower()
                provider = _PROVIDERS.get(ext)
                if provider:
                    data = provider.load(path)
                    logger.debug("Конфигурация загружена из %s (%s)", path, ext)
                    return data
                logger.warning("Неподдерживаемый формат файла конфигурации: %s", path)
                return {}

            # Последовательно загружаем и объединяем файлы в порядке приоритета
            if main_path and Path(main_path).exists():
                utils.deep_merge(config_data, load_from_path(main_path))
            else:
                logger.debug("Основной файл конфигурации не найден или не указан.")

            if env_path and Path(env_path).exists():
                utils.deep_merge(config_data, load_from_path(env_path))
            else:
                logger.debug("Конфигурационный файл окружения не найден.")

            if local_path and Path(local_path).exists():
                utils.deep_merge(config_data, load_from_path(local_path))
            else:
                logger.debug("Локальный файл конфигурации не найден или не указан.")

            return config_data
        finally:
            _cm.release_file_lock()

    config_data = _cm.load_config_safe(_do_load)

    if model is not None:
        if not utils._check_pydantic():
            raise OptionalDependencyError(
                "Pydantic is required for configuration validation. "
                "Install it with 'pip install chutils[pydantic]' or 'poetry add pydantic'.",
                dependency="pydantic"
            )
        return model(**config_data)

    return config_data


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
    # Гарантируем инициализацию путей
    if not _cm.paths_initialized:
        _cm.initialize_paths(utils.find_project_root)

    path: Optional[str] = None

    # Явный путь в cfg_file имеет высший приоритет
    if cfg_file:
        path = cfg_file
    else:
        main_path, env_path, local_path = _cm.get_config_paths()
        if save_to_local and local_path:
            path = local_path
            logger.debug("Для сохранения выбран локальный файл конфигурации: %s", path)
        else:
            path = main_path

    if path is None:
        logger.error("Невозможно сохранить значение: путь к файлу конфигурации не определен.")
        return False

    if not notify:
        # Фиксируем время внутреннего сохранения для подавления Hot-Reload
        _cm.mark_internal_save()
    ext = Path(path).suffix.lower()
    provider = _PROVIDERS.get(ext)

    if not provider:
        logger.warning("Сохранение для формата %s не поддерживается.", ext)
        return False

    _cm.acquire_file_lock()
    try:
        success = provider.save(path, section, key, value)
        if success:
            logger.debug("Ключ '%s' в секции '[%s]' обновлен в файле %s", key, section, path)
            # Сбрасываем кэш
            _cm.clear_cache()
            return True
    finally:
        _cm.release_file_lock()

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
