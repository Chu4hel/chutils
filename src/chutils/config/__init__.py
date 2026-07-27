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

import logging  # chutils: ignore[ChutilsIntegrationRule]
from typing import Any, TYPE_CHECKING, TypeVar

from .core import get_config, aget_config, save_config_value, asave_config_value
from .custom_providers import (
    BaseConfigProvider,
    DictConfigProvider,
)
from .getters import (
    get_config_value,
    aget_config_value,
    get_config_int,
    get_config_float,
    get_config_boolean,
    get_config_list,
    get_config_section,
    get_config_path,
    validate_required_keys
)
from .manager import _cm
from .utils import find_project_root
from .watcher import (
    on_config_change,
    start_config_watcher,
    stop_config_watcher,
)

if TYPE_CHECKING:
    from ..logger import ChutilsLogger
    from pydantic import BaseModel
    from .generator import (
        generate_yaml_template,
        generate_env_template,
        generate_json_schema,
    )
    from .schema import export_schema, import_model_class
    from .dev import (
        load_ai_lint_config as load_ai_lint_config,
        parse_chutils_ignore as parse_chutils_ignore,
    )

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
    'aget_config_value',
    'get_config_int',
    'get_config_float',
    'get_config_boolean',
    'get_config_list',
    'get_config_section',
    'get_config_path',
    'validate_required_keys',
    'get_base_dir',
    'get_config_file_path',
    'is_config_loaded',
    'are_paths_initialized',
    'get_config_paths',
    'get_all_config_paths',
    'on_config_change',
    'start_config_watcher',
    'stop_config_watcher',
    'generate_yaml_template',
    'generate_env_template',
    'generate_json_schema',
    'export_schema',
    'import_model_class',
    'load_ai_lint_config',
    'parse_chutils_ignore',
    'register_provider',
    'reset_providers',
    'BaseConfigProvider',
    'DictConfigProvider',
    'trigger_reload',
    'start_webhook_server',
    'stop_webhook_server',
    'SseConfigClient',
    'SseEvent',
    'parse_sse_lines',
    'WebhookConfigServer',
    'verify_webhook_request',
    'create_fastapi_webhook_route',
    'create_flask_webhook_route',
]


def _get_logger() -> 'ChutilsLogger':
    """
    Вспомогательная функция для получения типизированного логгера.

    Returns:
        Экземпляр логгера (может быть ChutilsLogger, если инициализирован).
    """
    from typing import cast
    return cast('ChutilsLogger', logger)


def __getattr__(name: str) -> Any:
    """
    Обеспечивает ленивую загрузку экспортируемых функций генератора и схемы.
    """
    lazy_imports = {
        'generate_yaml_template': ('.generator', 'generate_yaml_template'),
        'generate_env_template': ('.generator', 'generate_env_template'),
        'generate_json_schema': ('.generator', 'generate_json_schema'),
        'export_schema': ('.schema', 'export_schema'),
        'import_model_class': ('.schema', 'import_model_class'),
        'load_ai_lint_config': ('.dev', 'load_ai_lint_config'),
        'parse_chutils_ignore': ('.dev', 'parse_chutils_ignore'),
        'SseConfigClient': ('.sse', 'SseConfigClient'),
        'SseEvent': ('.sse', 'SseEvent'),
        'parse_sse_lines': ('.sse', 'parse_sse_lines'),
        'WebhookConfigServer': ('.webhook_server', 'WebhookConfigServer'),
        'verify_webhook_request': ('.webhook_server', 'verify_webhook_request'),
        'create_fastapi_webhook_route': ('.integrations', 'create_fastapi_webhook_route'),
        'create_flask_webhook_route': ('.integrations', 'create_flask_webhook_route'),
    }

    if name in lazy_imports:
        import importlib
        mod_path, attr_name = lazy_imports[name]
        module = importlib.import_module(mod_path, __package__ or __name__)
        return getattr(module, attr_name)

    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


def get_base_dir() -> str | None:
    """
    Возвращает абсолютный путь к корневой директории проекта.

    Если пути еще не инициализированы, запускает автоматический поиск.

    Returns:
        Путь к корню проекта или None, если корень не найден.
    """
    if not _cm.paths_initialized:
        _cm.initialize_paths(find_project_root)
    return _cm.base_dir


def get_config_file_path() -> str | None:
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


def get_config_paths(cfg_file: str | None = None) -> tuple[str | None, str | None]:
    """
    Возвращает пути к основному и локальному файлам конфигурации.

    Legacy API для обратной совместимости. Возвращает кортеж из 2 элементов.
    Для получения всех путей (включая env) используйте get_all_config_paths().

    Args:
        cfg_file: Опциональный путь к основному файлу.

    Returns:
        Кортеж (путь_к_основному, путь_к_локальному).
    """
    if not _cm.paths_initialized:
        _cm.initialize_paths(find_project_root)
    return _cm.get_config_paths(cfg_file)


def get_all_config_paths(cfg_file: str | None = None) -> tuple[str | None, str | None, str | None]:
    """
    Возвращает пути к основному, специфичному для окружения и локальному файлам конфигурации.

    Args:
        cfg_file: Опциональный путь к основному файлу.

    Returns:
        Кортеж (путь_к_основному, путь_к_окружению, путь_к_локальному).
    """
    if not _cm.paths_initialized:
        _cm.initialize_paths(find_project_root)
    return _cm.get_all_config_paths(cfg_file)


def register_provider(provider: 'BaseConfigProvider', priority: int = 100) -> None:
    """Регистрирует кастомный провайдер конфигурации.

    Провайдеры опрашиваются перед чтением локальных файлов конфигурации.
    Если провайдер возвращает значение (не ``None``), оно используется как итоговое.

    Приоритет: **меньшее число → выше приоритет** (опрашивается первым).

    Args:
        provider: Экземпляр класса, реализующего :class:`BaseConfigProvider`.
        priority: Числовой приоритет провайдера. По умолчанию: 100.

    Example:
        ::

            from chutils.config import register_provider
            from chutils.config.custom_providers import DictConfigProvider

            provider = DictConfigProvider({"db": {"host": "prod-db"}})
            register_provider(provider, priority=10)
    """
    _cm.register_provider(provider, priority)


def reset_providers() -> None:
    """Очищает реестр всех зарегистрированных кастомных провайдеров.

    Используется в тестах для сброса состояния между тест-кейсами,
    а также при необходимости переконфигурирования провайдеров в рантайме.

    Example:
        ::

            from chutils.config import reset_providers

            def teardown():
                reset_providers()
    """
    _cm.reset_providers()


def trigger_reload() -> None:
    """Вызывает принудительную перезагрузку конфигурации и оповещает колбэки."""
    _cm.trigger_reload()


def start_webhook_server(
    host: str = "0.0.0.0",
    port: int = 8080,
    path: str = "/webhook/config-reload",
    secret_token: str | None = None,
    hmac_secret: str | None = None,
) -> Any:
    """
    Запускает встроенный Webhook-сервер для мгновенного обновления конфигурации.

    Args:
        host: Хост прослушивания (по умолчанию 0.0.0.0).
        port: Порт прослушивания (0 — случайный порт).
        path: Путь эндпоинта (по умолчанию /webhook/config-reload).
        secret_token: Опциональный токен авторизации.
        hmac_secret: Опциональный секретный ключ HMAC-SHA256.

    Returns:
        Экземпляр WebhookConfigServer.
    """
    return _cm.start_webhook_server(
        host=host,
        port=port,
        path=path,
        secret_token=secret_token,
        hmac_secret=hmac_secret,
    )


def stop_webhook_server() -> None:
    """Останавливает запущенный встроенный Webhook-сервер."""
    _cm.stop_webhook_server()
