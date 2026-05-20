"""
Пакет chutils - набор переиспользуемых утилит для Python.

Основная цель - упростить рутинные задачи, такие как работа с конфигурацией,
логированием и управлением секретами, с минимальными усилиями со стороны разработчика.

Ключевые особенности:
- Автоматическое обнаружение корня проекта и файла конфигурации.
- Поддержка форматов `config.yml`, `config.yaml` и `config.ini` (YAML в приоритете).
- Удобные функции для доступа к настройкам, включая разрешение путей.
- Асинхронные версии основных функций для неблокирующей работы.
- Готовый к работе логгер с выводом в консоль и ротируемые файлы.
- Безопасное хранение секретов через системное хранилище (keyring).

Основное использование:
----------------------
Вам не нужно ничего инициализировать. Просто импортируйте и используйте:

    from chutils import get_config_value, setup_logger, SecretManager

    logger = setup_logger()
    secrets = SecretManager("my_app")
    db_host = get_config_value("Database", "host", "localhost")
    logger.info(f"Подключение к базе данных на {db_host}")

Ручная инициализация (для нестандартных случаев):
-------------------------------------------------
Если автоматика не сработала, вы можете указать путь к корню проекта вручную:

    import chutils
    chutils.init(base_dir="/path/to/your/project")

"""

import importlib
import os
from typing import Any

# Словарь соответствия имен атрибутов их модулям и именам внутри этих модулей.
# Формат: 'имя_атрибута': ('относительный_путь_к_модулю', 'имя_в_модуле' или None для самого модуля)
_LAZY_MAPPING = {
    # modules
    'config': ('.config', None),
    'logger': ('.logger', None),
    'secret_manager': ('.secret_manager', None),
    'decorators': ('.decorators', None),
    'cache': ('.cache', None),
    'exceptions': ('.exceptions', None),
    'context': ('.context', None),
    'lifecycle': ('.lifecycle', None),

    # config
    'get_config': ('.config', 'get_config'),
    'get_config_value': ('.config', 'get_config_value'),
    'get_config_int': ('.config', 'get_config_int'),
    'get_config_float': ('.config', 'get_config_float'),
    'get_config_boolean': ('.config', 'get_config_boolean'),
    'get_config_list': ('.config', 'get_config_list'),
    'get_config_section': ('.config', 'get_config_section'),
    'get_config_path': ('.config', 'get_config_path'),
    'aget_config': ('.config', 'aget_config'),
    'save_config_value': ('.config', 'save_config_value'),
    'asave_config_value': ('.config', 'asave_config_value'),
    'start_config_watcher': ('.config', 'start_config_watcher'),
    'stop_config_watcher': ('.config', 'stop_config_watcher'),
    'on_config_change': ('.config', 'on_config_change'),

    # logger
    'setup_logger': ('.logger', 'setup_logger'),
    'ChutilsLogger': ('.logger', 'ChutilsLogger'),
    'SafeTimedRotatingFileHandler': ('.logger', 'SafeTimedRotatingFileHandler'),

    # context
    'bind_context': ('.context', 'bind_context'),
    'unbind_context': ('.context', 'unbind_context'),
    'clear_context': ('.context', 'clear_context'),

    # lifecycle
    'register_cleanup': ('.lifecycle', 'register_cleanup'),
    'setup_graceful_shutdown': ('.lifecycle', 'setup_graceful_shutdown'),

    # secret_manager
    'SecretManager': ('.secret_manager', 'SecretManager'),

    # decorators
    'log_function_details': ('.decorators', 'log_function_details'),
    'retry': ('.decorators', 'retry'),
    'timeout': ('.decorators', 'timeout'),

    # exceptions
    'ChutilsException': ('.exceptions', 'ChutilsException'),
    'ConfigError': ('.exceptions', 'ConfigError'),
    'ConfigLoadError': ('.exceptions', 'ConfigLoadError'),
    'ConfigParseError': ('.exceptions', 'ConfigParseError'),
    'SecretError': ('.exceptions', 'SecretError'),
    'SecretNotFoundError': ('.exceptions', 'SecretNotFoundError'),
    'SecretProviderError': ('.exceptions', 'SecretProviderError'),
    'LoggerConfigurationError': ('.exceptions', 'LoggerConfigurationError'),
    'WatcherInitializationError': ('.exceptions', 'WatcherInitializationError'),
    'OptionalDependencyError': ('.exceptions', 'OptionalDependencyError'),
    'ChutilsTimeoutError': ('.exceptions', 'ChutilsTimeoutError'),
}


def __getattr__(name: str) -> Any:
    """
    Реализация ленивой загрузки согласно PEP 562.
    Вызывается при обращении к атрибутам модуля, которые не определены явно.
    """
    if name in _LAZY_MAPPING:
        mod_path, attr_name = _LAZY_MAPPING[name]
        module = importlib.import_module(mod_path, __name__)
        if attr_name is None:
            return module
        return getattr(module, attr_name)

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    """
    Возвращает список всех доступных атрибутов для поддержки автодополнения и интроспекции.
    """
    return sorted(list(_LAZY_MAPPING.keys()) + [
        'init', '__all__', '__doc__', '__file__', '__path__',
        '__name__', '__package__', '__spec__'
    ])


def init(base_dir: str):
    """
    Ручная инициализация пакета с указанием базовой директории проекта.

    Эту функцию нужно вызывать только в том случае, если автоматическое
    определение корня проекта не сработало. Вызывать следует один раз
    в самом начале работы основного скрипта вашего приложения.

    Args:
        base_dir (str): Абсолютный путь к корневой директории проекта.

    Raises:
        ChutilsException: Если указанная директория не существует.
    """
    if not os.path.isdir(base_dir):
        # Импортируем исключение лениво
        from .exceptions import ChutilsException
        raise ChutilsException(
            f"Указанная директория base_dir не существует или не является директорией: {base_dir}",
            base_dir=base_dir
        )

    # Вручную устанавливаем базовую директорию через менеджер состояний.
    from .config.manager import _cm
    _cm.base_dir = base_dir
    _cm.paths_initialized = True

    print(f"Пакет chutils вручную инициализирован с базовой директорией: {base_dir}")


# --- Определение публичного API (`__all__`) ---
__all__ = list(_LAZY_MAPPING.keys()) + ['init']
