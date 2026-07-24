"""
Ядро системы конфигурации.

Обеспечивает оркестрацию загрузки из разных источников (основной файл, 
специфичный для окружения, локальный, переменные окружения) и сохранение значений.
"""

from __future__ import annotations

import asyncio
import functools
import logging  # chutils: ignore[ChutilsIntegrationRule]
import os
from pathlib import Path
from typing import Any, TYPE_CHECKING, TypeVar

from chutils.exceptions import OptionalDependencyError
from chutils.typing import JSONDict
from . import utils
from .manager import _cm
from .providers import get_providers, HttpConfigProvider

if TYPE_CHECKING:
    from pydantic import BaseModel

# Тип для Pydantic моделей
T = TypeVar("T", bound="BaseModel")

logger = logging.getLogger(__name__)

# Реестр провайдеров (использует _nest_ini_dict из utils)
_PROVIDERS = get_providers(utils._nest_ini_dict)

_config_plugins_loaded = False


def _ensure_config_plugins_loaded() -> None:
    """Лениво загружает плагины конфигурации и добавляет их в _PROVIDERS."""
    global _PROVIDERS, _config_plugins_loaded
    if not _config_plugins_loaded:
        _config_plugins_loaded = True
        try:
            from ..plugins import registry, ConfigProviderPlugin
            registry.discover_plugins("chutils.plugins.config")
            external_providers = registry.get_plugins_by_type(ConfigProviderPlugin)
            for provider in external_providers:
                extensions = []
                if hasattr(provider, "supported_extensions"):
                    extensions = provider.supported_extensions
                else:
                    ext = provider.name
                    if not ext.startswith("."):
                        ext = f".{ext}"
                    extensions = [ext]

                for ext in extensions:
                    ext_lower = ext.lower()
                    if ext_lower not in _PROVIDERS:
                        _PROVIDERS[ext_lower] = provider
                        logger.debug("Зарегистрирован внешний ConfigProvider для расширения %s", ext_lower)
        except Exception as e:
            logger.error("Ошибка при загрузке плагинов конфигурации: %s", str(e))


def _enrich_config_data_with_pydantic_aliases(
    config_data: JSONDict,
    model: type[Any],
    section_prefix: str = ""
) -> None:
    """
    Обогащает словарь конфигурации значениями из переменных окружения
    с учетом имени полей и их алиасов (включая Pydantic AliasChoices).

    Args:
        config_data: Загруженный словарь конфигурации для обогащения.
        model: Pydantic модель.
        section_prefix: Префикс текущей секции для поиска переменных окружения.
    """
    import os
    from typing import get_args, get_origin

    disable_env_override = os.getenv("CH_DISABLE_ENV_OVERRIDE", "").lower() in ("true", "1", "yes", "y")

    fields = getattr(model, "model_fields", None)
    if fields is None:
        fields = getattr(model, "__fields__", {})

    for field_name, field_info in fields.items():
        annotation = getattr(field_info, "annotation", None)
        if annotation is None:
            annotation = getattr(field_info, "type_", None)

        origin = get_origin(annotation)
        if origin is not None:
            args = [a for a in get_args(annotation) if a is not type(None)]
            if args:
                annotation = args[0]

        if isinstance(annotation, type) and (hasattr(annotation, "model_fields") or hasattr(annotation, "__fields__")):
            sec_dict = config_data.get(field_name)
            if not isinstance(sec_dict, dict):
                for k, v in config_data.items():
                    if k.lower() == field_name.lower() and isinstance(v, dict):
                        sec_dict = v
                        break
                else:
                    sec_dict = {}
                    config_data[field_name] = sec_dict

            new_prefix = f"{section_prefix}_{field_name}" if section_prefix else field_name
            _enrich_config_data_with_pydantic_aliases(sec_dict, annotation, section_prefix=new_prefix)
            continue

        aliases: list[str] = [field_name]

        val_alias = getattr(field_info, "validation_alias", None)
        if val_alias is None:
            val_alias = getattr(field_info, "alias", None)

        if isinstance(val_alias, str):
            if val_alias not in aliases:
                aliases.append(val_alias)
        elif hasattr(val_alias, "choices"):
            choices = getattr(val_alias, "choices", [])
            for choice in choices:
                if isinstance(choice, str) and choice not in aliases:
                    aliases.append(choice)

        found_key = None
        for alias in aliases:
            if alias in config_data:
                found_key = alias
                break
            for k in config_data.keys():
                if k.lower() == alias.lower():
                    found_key = k
                    break
            if found_key:
                break

        if found_key is None and not disable_env_override:
            for alias in aliases:
                key_up = alias.upper()
                candidates: list[str] = []
                if section_prefix:
                    sec_up = section_prefix.upper()
                    candidates.append(f"CH_{sec_up}_{key_up}")
                candidates.extend([f"CH_{key_up}", key_up])

                env_val = None
                for cand in candidates:
                    if cand in os.environ and os.environ[cand] != "":
                        env_val = os.environ[cand]
                        break

                if env_val is not None:
                    for a in aliases:
                        config_data[a] = env_val
                    break


def get_config(
        model: type[T] | None = None,
        remote_url: str | None = None,
        remote_auth: tuple[str, str] | None = None,
        polling_interval: int | None = None,
        sse_url: str | None = None,
        sse_headers: dict[str, str] | None = None,
) -> JSONDict | T:
    """
    Загружает и объединяет конфигурацию из всех доступных источников.

    Результат кэшируется. Повторные вызовы возвращают кэшированный объект,
    если он не был сброшен (например, при сохранении нового значения).

    Порядок применения конфигураций (от меньшего приоритета к большему):
    1. Основной файл (config.yml)
    2. Файл окружения (config.{CH_ENV}.yml)
    3. Локальный файл (config.local.yml)
    4. Удаленный источник (если указан remote_url)
    5. Переменные окружения (CH_SECTION_KEY)

    Args:
        model: Опциональный класс Pydantic модели для валидации.
        remote_url: URL для загрузки удаленной конфигурации.
        remote_auth: Кортеж (login, password) для Basic Auth.
        polling_interval: Интервал опроса удаленного источника в секундах.
            Если не указан, опрос не запускается.
        sse_url: URL для подключения к SSE-серверу событий об обновлениях.
        sse_headers: HTTP-заголовки для подключений к SSE-серверу.

    Returns:
       Словарь со всей конфигурацией проекта или экземпляр Pydantic модели.
       Если файлы не найдены, возвращается пустой словарь (или ошибка валидации модели).

    Raises:
        ConfigLoadError: Если произошла ошибка при чтении файлов конфигурации.
        ConfigParseError: Если файлы конфигурации содержат синтаксические ошибки.
        OptionalDependencyError: Если передана `model`, но пакет `pydantic` не установлен.
    """

    def _do_load() -> JSONDict:
        # Гарантируем инициализацию путей
        if not _cm.paths_initialized:
            _cm.initialize_paths(utils.find_project_root)

        _cm.acquire_file_lock()
        try:
            main_path, env_path, local_path = _cm.get_all_config_paths()
            config_data: JSONDict = {}

            def load_from_path(path: str) -> JSONDict:
                ext = Path(path).suffix.lower()
                _ensure_config_plugins_loaded()
                provider = _PROVIDERS.get(ext)
                if provider:
                    data = provider.load(path)
                    logger.debug("Конфигурация загружена из %s (%s)", path, ext)
                    return data
                logger.warning("Неподдерживаемый формат файла конфигурации: %s", path)
                return {}

            # Последовательно загружаем и объединяем файлы в порядке приоритета
            if main_path and Path(main_path).exists():
                data = load_from_path(main_path)
                _cm.record_trace_dict(data, main_path)
                utils.deep_merge(config_data, data)
            else:
                logger.debug("Основной файл конфигурации не найден или не указан.")

            if env_path and Path(env_path).exists():
                data = load_from_path(env_path)
                _cm.record_trace_dict(data, env_path)
                utils.deep_merge(config_data, data)
            else:
                logger.debug("Конфигурационный файл окружения не найден.")

            if local_path and Path(local_path).exists():
                data = load_from_path(local_path)
                _cm.record_trace_dict(data, local_path)
                utils.deep_merge(config_data, data)
            else:
                logger.debug("Локальный файл конфигурации не найден или не указан.")

            # 4. Удаленный источник (HttpConfigProvider)
            if remote_url:
                username, password = remote_auth if remote_auth else (None, None)
                if not _cm.remote_provider or _cm.remote_provider.url != remote_url:
                    # Останавливаем старый опрос, если был
                    if _cm.remote_provider:
                        _cm.remote_provider.stop_polling()

                    provider = HttpConfigProvider(
                        url=remote_url,
                        username=username,
                        password=password,
                        nest_func=utils._nest_ini_dict
                    )
                    _cm.remote_provider = provider

                    if polling_interval:
                        provider.start_polling(interval=polling_interval)

                try:
                    remote_data = _cm.remote_provider.load()
                    _cm.record_trace_dict(remote_data, remote_url)
                    utils.deep_merge(config_data, remote_data)
                except Exception as e:
                    logger.error("Ошибка загрузки удаленной конфигурации с %s: %s", remote_url, e)

            if sse_url:
                if not _cm.sse_client or _cm.sse_client.url != sse_url:
                    if _cm.sse_client:
                        _cm.sse_client.stop()
                    from .sse import SseConfigClient
                    sse_client = SseConfigClient(
                        url=sse_url,
                        headers=sse_headers,
                        on_reload=_cm.trigger_reload,
                    )
                    _cm.sse_client = sse_client
                    sse_client.start()

            # 5. Переменные окружения (CH_SECTION_KEY)
            disable_env_override = os.getenv("CH_DISABLE_ENV_OVERRIDE", "").lower() in ("true", "1", "yes", "y")  # chutils: ignore[ChutilsIntegrationRule]
            if not disable_env_override:
                env_overrides: JSONDict = {}
                for env_key, env_value in os.environ.items():  # chutils: ignore[ChutilsIntegrationRule]
                    if env_key.startswith("CH_") and env_key not in ("CH_ENV", "CH_DISABLE_ENV_OVERRIDE",
                                                                     "CH_DISABLE_KEYRING_WARNING"):
                        full_content = env_key[3:]
                        if not full_content:
                            continue

                        # Поиск подходящего разбиения на секцию и ключ
                        # Находим все индексы '_'
                        indices = [i for i, char in enumerate(full_content) if char == '_']

                        best_match = None
                        # Проверяем варианты от самого длинного имени секции к самому короткому
                        # (это позволяет корректно обрабатывать вложенность или длинные имена)
                        for idx in reversed(indices):
                            s_candidate = full_content[:idx]
                            k_candidate = full_content[idx + 1:]
                            if not s_candidate or not k_candidate:
                                continue

                            # Проверяем, есть ли такая секция (регистронезависимо)
                            for existing_sec in config_data.keys():
                                if existing_sec.lower() == s_candidate.lower():
                                    # Нашли существующую секцию. Теперь поищем ключ в ней.
                                    actual_sec = existing_sec
                                    actual_key = k_candidate.lower()

                                    if isinstance(config_data[existing_sec], dict):
                                        for existing_key in config_data[existing_sec].keys():
                                            if existing_key.lower() == k_candidate.lower():
                                                actual_key = existing_key
                                                break

                                    best_match = (actual_sec, actual_key)
                                    break
                            if best_match:
                                break

                        if best_match:
                            actual_sec, actual_key = best_match
                        else:
                            # Если совпадений с существующими секциями нет,
                            # используем стандартный сплит по первому '_'
                            parts = full_content.split('_', 1)
                            if len(parts) == 2:
                                actual_sec, actual_key = parts[0].lower(), parts[1].lower()
                            else:
                                continue

                        if actual_sec not in env_overrides:
                            env_overrides[actual_sec] = {}
                        env_overrides[actual_sec][actual_key] = env_value

                # Специфический ключ для secrets
                secrets_env = os.getenv("CH_DISABLE_KEYRING_WARNING")  # chutils: ignore[ChutilsIntegrationRule]
                if secrets_env is not None:
                    if "secrets" not in env_overrides:
                        env_overrides["secrets"] = {}
                    env_overrides["secrets"]["disable_keyring"] = secrets_env

                if env_overrides:
                    utils.deep_merge(config_data, env_overrides)

            # Записываем переменные окружения в трассировку
            if _cm.tracing_enabled:
                _cm.trace_env_vars()

            return config_data
        finally:
            _cm.release_file_lock()

    config_data = _cm.load_config_safe(_do_load)

    if model is not None:
        from chutils.env import has_pydantic
        if not has_pydantic():
            raise OptionalDependencyError(
                "Pydantic is required for configuration validation.",
                dependency="pydantic",
                hint="Install it with 'pip install chutils[pydantic]' or 'poetry add pydantic'."
            )
        _enrich_config_data_with_pydantic_aliases(config_data, model)
        return model(**config_data)

    return config_data


_config_async_lock: asyncio.Lock | None = None


def _get_config_async_lock() -> asyncio.Lock:
    global _config_async_lock
    if _config_async_lock is None:
        _config_async_lock = asyncio.Lock()
    return _config_async_lock


async def aget_config(model: type[T] | None = None) -> JSONDict | T:
    """
    Асинхронная версия get_config.

    Args:
        model: Опциональный класс Pydantic модели для валидации.

    Returns:
        Словарь конфигурации или экземпляр Pydantic модели.
    """
    async with _get_config_async_lock():
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, functools.partial(get_config, model=model))


def save_config_value(
        section: str,
        key: str,
        value: Any,
        cfg_file: str | None = None,
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

    path: str | None = None

    # Явный путь в cfg_file имеет высший приоритет
    if cfg_file:
        path = cfg_file
    else:
        main_path, _, local_path = _cm.get_all_config_paths()
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
    _ensure_config_plugins_loaded()
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
        cfg_file: str | None = None,
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
    async with _get_config_async_lock():
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            functools.partial(save_config_value, section, key, value, cfg_file, save_to_local, notify)
        )
