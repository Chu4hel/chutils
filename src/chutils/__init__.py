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
    'time': ('.time', None),
    'tracing': ('.tracing', None),
    'testing': ('.testing', None),
    'dev': ('.dev', None),
    'Scaffolder': ('.dev.scaffold', 'Scaffolder'),
    'MockServerRunner': ('.dev.mock_server', 'MockServerRunner'),
    'generate_few_shot': ('.dev.few_shot', None),
    'few_shot': ('.dev.few_shot', None),
    'profile_imports': ('.dev.profile_imports', None),
    'dashboard': ('.dev.dashboard', None),
    'generate_workflow_yaml': ('.dev.github_actions', 'generate_workflow_yaml'),
    'events': ('.events', None),
    'tasks': ('.tasks', None),
    'text': ('.text', None),
    'crypto': ('.crypto', None),
    'fs': ('.fs', None),
    'diagnostics': ('.diagnostics', None),
    'DiagnosticsManager': ('.diagnostics', 'DiagnosticsManager'),
    'validation': ('.validation', None),
    'http': ('.http', None),

    # http
    'HttpClient': ('.http', 'HttpClient'),
    'AsyncHttpClient': ('.http', 'AsyncHttpClient'),
    'HttpResponse': ('.http', 'HttpResponse'),
    'ResiliencePolicy': ('.http', 'ResiliencePolicy'),
    'UrllibFallbackClient': ('.http', 'UrllibFallbackClient'),
    'inject_trace_headers': ('.http', 'inject_trace_headers'),
    'create_http_span': ('.http', 'create_http_span'),

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
    'generate_yaml_template': ('.config', 'generate_yaml_template'),
    'generate_env_template': ('.config', 'generate_env_template'),
    'generate_json_schema': ('.config', 'generate_json_schema'),
    'get_base_dir': ('.config', 'get_base_dir'),
    'get_config_file_path': ('.config', 'get_config_file_path'),
    'is_config_loaded': ('.config', 'is_config_loaded'),
    'are_paths_initialized': ('.config', 'are_paths_initialized'),
    'get_config_paths': ('.config', 'get_config_paths'),
    'get_all_config_paths': ('.config', 'get_all_config_paths'),
    'export_schema': ('.config', 'export_schema'),
    'load_ai_lint_config': ('.config', 'load_ai_lint_config'),
    'parse_chutils_ignore': ('.config', 'parse_chutils_ignore'),
    'validate_required_keys': ('.config', 'validate_required_keys'),
    'register_provider': ('.config', 'register_provider'),
    'reset_providers': ('.config', 'reset_providers'),
    'aget_config_value': ('.config', 'aget_config_value'),
    'BaseConfigProvider': ('.config', 'BaseConfigProvider'),
    'DictConfigProvider': ('.config', 'DictConfigProvider'),

    # features
    'is_feature_enabled': ('.features', 'is_feature_enabled'),
    'require_feature': ('.features', 'require_feature'),

    # logger
    'setup_logger': ('.logger', 'setup_logger'),
    'setup_logger_from_config': ('.logger', 'setup_logger_from_config'),
    'ChutilsLogger': ('.logger', 'ChutilsLogger'),
    'LogLevel': ('.logger', 'LogLevel'),
    'SecretMaskingFilter': ('.logger', 'SecretMaskingFilter'),
    'ChutilsJsonFormatter': ('.logger', 'ChutilsJsonFormatter'),
    'SafeTimedRotatingFileHandler': ('.logger', 'SafeTimedRotatingFileHandler'),
    'CompressingRotatingFileHandler': ('.logger', 'CompressingRotatingFileHandler'),
    'CompressingTimedRotatingFileHandler': ('.logger', 'CompressingTimedRotatingFileHandler'),
    'DEVDEBUG_LEVEL_NUM': ('.logger', 'DEVDEBUG_LEVEL_NUM'),
    'MEDIUMDEBUG_LEVEL_NUM': ('.logger', 'MEDIUMDEBUG_LEVEL_NUM'),

    # cli_utils
    'get_console': ('.cli_utils', 'get_console'),

    # env (Discovery)
    'is_rich_enabled': ('.env', 'is_rich_enabled'),
    'is_otel_enabled': ('.env', 'is_otel_enabled'),
    'RICH_AVAILABLE': ('.env', 'RICH_AVAILABLE'),
    'PYDANTIC_AVAILABLE': ('.env', 'PYDANTIC_AVAILABLE'),
    'WATCHDOG_AVAILABLE': ('.env', 'WATCHDOG_AVAILABLE'),
    'JSON_LOGGER_AVAILABLE': ('.env', 'JSON_LOGGER_AVAILABLE'),
    'OTEL_AVAILABLE': ('.env', 'OTEL_AVAILABLE'),
    'BaseEnvManifest': ('.env', 'BaseEnvManifest'),

    # cache
    'cache_with_ttl': ('.cache', 'cache_with_ttl'),
    'BaseCacheBackend': ('.cache', 'BaseCacheBackend'),
    'InMemoryCacheBackend': ('.cache', 'InMemoryCacheBackend'),

    # context
    'bind_context': ('.context', 'bind_context'),
    'unbind_context': ('.context', 'unbind_context'),
    'clear_context': ('.context', 'clear_context'),

    # lifecycle
    'register_cleanup': ('.lifecycle', 'register_cleanup'),
    'setup_graceful_shutdown': ('.lifecycle', 'setup_graceful_shutdown'),

    # cli_booster
    'cli_command': ('.cli_booster', 'cli_command'),

    # time
    'utc_now': ('.time', 'utc_now'),
    'parse_datetime': ('.time', 'parse_datetime'),
    'humanize_timedelta': ('.time', 'humanize_timedelta'),

    # secret_manager
    'SecretManager': ('.secret_manager', 'SecretManager'),

    # decorators
    'log_function_details': ('.decorators', 'log_function_details'),
    'retry': ('.decorators', 'retry'),
    'timeout': ('.decorators', 'timeout'),
    'rate_limit': ('.decorators', 'rate_limit'),
    'circuit_breaker': ('.decorators', 'circuit_breaker'),
    'semaphore': ('.decorators', 'semaphore'),
    'bulkhead': ('.decorators', 'bulkhead'),

    # tracing
    'trace': ('.tracing', 'trace'),
    'setup_tracing': ('.tracing', 'setup_tracing'),
    'IS_OTEL_AVAILABLE': ('.tracing', 'IS_OTEL_AVAILABLE'),

    # exceptions
    'ChutilsException': ('.exceptions', 'ChutilsException'),
    'ChutilsConfigurationError': ('.exceptions', 'ChutilsConfigurationError'),
    'ConfigError': ('.exceptions', 'ConfigError'),
    'ConfigLoadError': ('.exceptions', 'ConfigLoadError'),
    'ConfigParseError': ('.exceptions', 'ConfigParseError'),
    'ConfigKeyNotFoundError': ('.exceptions', 'ConfigKeyNotFoundError'),
    'ConfigValidationGroupError': ('.exceptions', 'ConfigValidationGroupError'),
    'SecretError': ('.exceptions', 'SecretError'),
    'SecretNotFoundError': ('.exceptions', 'SecretNotFoundError'),
    'SecretProviderError': ('.exceptions', 'SecretProviderError'),
    'LoggerConfigurationError': ('.exceptions', 'LoggerConfigurationError'),
    'WatcherInitializationError': ('.exceptions', 'WatcherInitializationError'),
    'OptionalDependencyError': ('.exceptions', 'OptionalDependencyError'),
    'ChutilsTimeoutError': ('.exceptions', 'ChutilsTimeoutError'),
    'RateLimitExceededError': ('.exceptions', 'RateLimitExceededError'),
    'CircuitBreakerOpenError': ('.exceptions', 'CircuitBreakerOpenError'),
    'BulkheadLimitExceeded': ('.exceptions', 'BulkheadLimitExceeded'),
    'CacheError': ('.exceptions', 'CacheError'),
    'EventBusError': ('.exceptions', 'EventBusError'),
    'EventBusExceptionGroup': ('.exceptions', 'EventBusExceptionGroup'),
    'ChutilsValidationError': ('.exceptions', 'ChutilsValidationError'),
    'EnvValidationError': ('.exceptions', 'EnvValidationError'),
    'HttpClientError': ('.exceptions', 'HttpClientError'),

    # events
    'subscribe': ('.events', 'subscribe'),
    'publish': ('.events', 'publish'),
    'publish_async': ('.events', 'publish_async'),
    'ErrorStrategy': ('.events', 'ErrorStrategy'),
    'EventBus': ('.events', 'EventBus'),

    # tasks
    'periodic_task': ('.tasks', 'periodic_task'),
    'start_scheduler': ('.tasks', 'start_scheduler'),
    'stop_scheduler': ('.tasks', 'stop_scheduler'),

    # di
    'di': ('.di', None),
    'Container': ('.di.container', 'Container'),
    'provide': ('.di.container', 'provide'),
    'inject': ('.di.container', 'inject'),
    'Inject': ('.di.container', 'Inject'),
    'container': ('.di.container', 'default_container'),

    # metrics
    'metrics': ('.metrics', None),

    # text
    'natsort_key': ('.text', 'natsort_key'),
    'is_significant_difference': ('.text', 'is_significant_difference'),

    # crypto
    'encrypt_portable': ('.crypto', 'encrypt_portable'),
    'decrypt_portable': ('.crypto', 'decrypt_portable'),
    'encrypt_file': ('.crypto', 'encrypt_file'),
    'decrypt_file': ('.crypto', 'decrypt_file'),

    # fs
    'remove_path': ('.fs', 'remove_path'),
    'cleanup_paths': ('.fs', 'cleanup_paths'),
    'safe_filename': ('.fs', 'safe_filename'),
    'zip_folder': ('.fs', 'zip_folder'),

    # validation
    'validate_data': ('.validation', 'validate_data'),
    'validate_call': ('.validation', 'validate_call'),

    # web
    'web': ('.web', None),
    'WebClient': ('.web', 'WebClient'),
    'AsyncWebClient': ('.web', 'AsyncWebClient'),

    # scraping
    'scraping': ('.scraping', None),
    'BezierCurveGenerator': ('.scraping.humanize', 'BezierCurveGenerator'),
    'JitterDelayGenerator': ('.scraping.humanize', 'JitterDelayGenerator'),
    'KeyboardTypoGenerator': ('.scraping.humanize', 'KeyboardTypoGenerator'),
    'human_sleep': ('.scraping.humanize', 'human_sleep'),
    'async_human_sleep': ('.scraping.humanize', 'async_human_sleep'),
    'async_move_mouse': ('.scraping.humanize', 'async_move_mouse'),
    'async_scroll_to': ('.scraping.humanize', 'async_scroll_to'),
    'async_type_text': ('.scraping.humanize', 'async_type_text'),
    'move_mouse': ('.scraping.humanize', 'move_mouse'),
    'scroll_to': ('.scraping.humanize', 'scroll_to'),
    'type_text': ('.scraping.humanize', 'type_text'),
    'apply_antidetect_playwright': ('.scraping.humanize', 'apply_antidetect_playwright'),
    'apply_antidetect_selenium': ('.scraping.humanize', 'apply_antidetect_selenium'),
    'get_browser_launch_args': ('.scraping.humanize', 'get_browser_launch_args'),

    # scraping captcha
    'RuCaptchaSolver': ('.scraping.captcha', 'RuCaptchaSolver'),
    'AsyncRuCaptchaSolver': ('.scraping.captcha', 'AsyncRuCaptchaSolver'),
    'AntiCaptchaSolver': ('.scraping.captcha', 'AntiCaptchaSolver'),
    'AsyncAntiCaptchaSolver': ('.scraping.captcha', 'AsyncAntiCaptchaSolver'),
    'CapMonsterSolver': ('.scraping.captcha', 'CapMonsterSolver'),
    'AsyncCapMonsterSolver': ('.scraping.captcha', 'AsyncCapMonsterSolver'),
    'CaptchaError': ('.scraping.captcha', 'CaptchaError'),
    'CaptchaTimeoutError': ('.scraping.captcha', 'CaptchaTimeoutError'),
    'CaptchaBalanceError': ('.scraping.captcha', 'CaptchaBalanceError'),
    'CaptchaServiceError': ('.scraping.captcha', 'CaptchaServiceError'),

    # db
    'db': ('.db', None),
    'DatabaseManager': ('.db', 'DatabaseManager'),

    # audit
    'audit': ('.audit', None),
    'AuditEvent': ('.audit', 'AuditEvent'),
    'BaseAuditBackend': ('.audit', 'BaseAuditBackend'),
    'FileBackend': ('.audit', 'FileBackend'),
    'SqliteBackend': ('.audit', 'SqliteBackend'),
    'PostgresBackend': ('.audit', 'PostgresBackend'),
    'audit_event': ('.audit', 'audit_event'),
    'audit_context': ('.audit', 'audit_context'),
    'AuditError': ('.exceptions', 'AuditError'),
    'AuditIntegrityError': ('.exceptions', 'AuditIntegrityError'),

    # plugins
    'plugins': ('.plugins', None),
    'register_plugin': ('.plugins', 'register_plugin'),
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

    # Поддержка импорта субмодулей (например, для unittest.mock.patch в Python 3.10)
    try:
        import importlib.util as importlib_util
        spec = importlib_util.find_spec(f".{name}", __name__)
        if spec is not None:
            return importlib.import_module(f".{name}", __name__)
    except Exception:
        pass

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    """
    Возвращает список всех доступных атрибутов для поддержки автодополнения и интроспекции.
    """
    return sorted(list(_LAZY_MAPPING.keys()) + [
        'init', '__all__', '__doc__', '__file__', '__path__',
        '__name__', '__package__', '__spec__'
    ])


def init(base_dir: str) -> None:
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
