# Справочник API

В этом разделе находится документация, автоматически сгенерированная из исходного кода `chutils`.
Все детали реализации, приоритеты настроек и примеры перенесены непосредственно в докстринги модулей и функций.

## Пакет `chutils`

::: chutils
options:
members: [init]

## Модуль `config`

::: chutils.config
options:
members:

- get_config
- aget_config
- get_config_value
- aget_config_value
- HttpConfigProvider
- get_config_int
- get_config_float
- get_config_boolean
- get_config_list
- get_config_section
- get_config_path
- save_config_value
- asave_config_value
- start_config_watcher
- stop_config_watcher
- on_config_change
- get_base_dir
- get_config_file_path
- is_config_loaded
- are_paths_initialized
- get_config_paths
- generate_yaml_template
- generate_env_template
- generate_json_schema
- export_schema
- import_model_class
- register_provider
- reset_providers
- BaseConfigProvider
- DictConfigProvider
- trigger_reload
- start_webhook_server
- stop_webhook_server
- SseConfigClient
- WebhookConfigServer
- verify_webhook_request
- create_fastapi_webhook_route
- create_flask_webhook_route

## Модуль `config.custom_providers` (Custom Config Providers API)

::: chutils.config.custom_providers
options:
members:

- BaseConfigProvider
- DictConfigProvider

## Модуль `logger`

::: chutils.logger
options:
members:

- setup_logger
- ChutilsLogger
- DEVDEBUG_LEVEL_NUM
- MEDIUMDEBUG_LEVEL_NUM

## Модуль `context`

::: chutils.context
options:
members:

- bind_context
- unbind_context
- clear_context
- ContextFilter

## Модуль `lifecycle` (Управление жизненным циклом)

::: chutils.lifecycle
options:
members:

- register_cleanup
- setup_graceful_shutdown
- run_cleanup
- async_run_cleanup
- lifecycle
- async_lifecycle
- AsyncLifecycleContext

## Модуль `cli_booster` (Быстрое создание CLI)

::: chutils.cli_booster
options:
members:

- cli_command

## Модуль `time` (Работа со временем)

::: chutils.time
options:
members:

- utc_now
- parse_datetime
- humanize_timedelta

## Модуль `tracing` (Распределенное трассирование)

::: chutils.tracing
options:
members:

- trace
- setup_tracing
- IS_OTEL_AVAILABLE

## Модуль `features` (Фича-флаги)

::: chutils.features
options:
members:

- is_feature_enabled
- require_feature

## Модуль `cache` (Умное кэширование)

::: chutils.cache
options:
members:

- cache_with_ttl
- BaseCacheBackend
- InMemoryCacheBackend

## Модуль `secret_manager`

::: chutils.secret_manager

## Модуль `config.diagnostics` (Отладка конфигурации)

::: chutils.config.diagnostics
handler: python

## Модуль `fs`

::: chutils.fs
options:
members:

- ensure_dir
- atomic_write
- get_temp_file

## Модуль `crypto` (Шифрование данных и файлов)

::: chutils.crypto
options:
members:

- encrypt_portable
- decrypt_portable
- encrypt_file
- decrypt_file

## Модуль `telegram` (Интеграция и контроль доступа Telegram-ботов)

::: chutils.telegram
options:
members:

- is_admin
- admin_only
- AdminFilter
- SecretUserFilter
- TelegramRateLimiter
- tg_rate_limit
- TelegramThrottlingMiddleware
- TelegramLoggingMiddleware
- AccessListManager
- allowed_only
- trace_telegram_update
- escape_markdown
- escape_html
- smart_truncate
- split_message
- TelegramLogHandler
- HealthCheckAlertBridge
- send_alert

## Декораторы

::: chutils.decorators
options:
members:

- retry
- log_function_details
- timeout
- rate_limit
- circuit_breaker

## Модуль `events` (Шина событий)

::: chutils.events
options:
members:

- EventBus
- ErrorStrategy
- subscribe
- publish
- publish_async

## Модуль `tasks` (Планировщик фоновых задач)

::: chutils.tasks
options:
members:

- periodic_task
- start_scheduler
- stop_scheduler
- ErrorStrategy

## Модуль `di` (Внедрение зависимостей)

::: chutils.di
options:
members:

- Container
- provide
- inject
- Inject

## Модуль `metrics` (Абстракция для метрик)

::: chutils.metrics
options:
members:

- increment
- set_gauge
- observe
- timer
- generate_latest
- get_provider
- set_provider
- clear

## Исключения

::: chutils.exceptions

## Тестирование

Подробную информацию о pytest-фикстурах для тестирования приложений с `chutils` см. в
разделе [Тестирование с chutils](./testing.md).

::: chutils.testing

## Модуль `dev` (AI-валидация и аудит)

::: chutils.dev
options:
members:

- Rule
- LintResult
- LinterEngine
- collect_context_slice
- run_interactive_menu
- generate_few_shot_bank
- MockServerRunner
- Scaffolder
- generate_workflow_yaml

## Модуль `diagnostics` (Мониторинг работоспособности)

::: chutils.diagnostics
options:
members:

- DiagnosticsManager
- CheckResult
- HealthReport
- get_fastapi_health_handler
- get_flask_health_handler

## Модуль `env` (Манифест окружения)

::: chutils.env
options:
members:

- BaseEnvManifest
- is_rich_enabled
- is_otel_enabled

## Модуль `validation` (Валидация данных)

::: chutils.validation
options:
members:

- validate_data
- validate_call

## Модуль `web` (Умный HTTP-клиент)

::: chutils.web
options:
members:

- WebClient
- AsyncWebClient

## Модуль `scraping.humanize` (Имитация поведения человека)

::: chutils.scraping.humanize
options:
members:

- BezierCurveGenerator
- JitterDelayGenerator
- KeyboardTypoGenerator
- human_sleep
- async_human_sleep
- move_mouse
- async_move_mouse
- scroll_to
- async_scroll_to
- type_text
- async_type_text
- apply_antidetect_playwright
- apply_antidetect_selenium
- get_browser_launch_args

## Модуль `scraping.captcha` (Решатели капчи)

::: chutils.scraping.captcha
options:
members:

- RuCaptchaSolver
- AsyncRuCaptchaSolver
- AntiCaptchaSolver
- AsyncAntiCaptchaSolver
- CapMonsterSolver
- AsyncCapMonsterSolver
- CaptchaError
- CaptchaTimeoutError
- CaptchaBalanceError
- CaptchaServiceError

## Модуль `plugins` (Система плагинов)

::: chutils.plugins
options:
members:

- register_plugin
- registry
- BasePlugin
- SecretProviderPlugin
- ConfigProviderPlugin
- LoggerHandlerPlugin
- MetricsPlugin

## Модуль `http` (HTTP-клиент и отказоустойчивость)

::: chutils.http
options:
members:

- HttpClient
- AsyncHttpClient
- ResiliencePolicy
- HttpResponse
- get
- post
- put
- delete
- patch

## Модуль `dev` (Инструменты разработчика и Live Dev)

::: chutils.dev
options:
members:

- BaseWatcher
- PollingWatcher
- WatchdogWatcher
- get_watcher
- BaseRunner
- SubprocessRunner
- InProcessReloader
- LinterEngine
- MockServerRunner

## Модуль `scraping.concurrency` (Умная очередь задач и воркеры)

::: chutils.scraping.concurrency
options:
members:

- ScrapingTask
- BaseTaskQueue
- InMemoryTaskQueue
- PersistentTaskQueue
- RedisTaskQueue
- DomainRateLimiter
- WorkerPool

## Модуль `qt` (Интеграция PyQt6 / PySide6)

::: chutils.qt
options:
members:

- QT_BINDING
- require_qt
- QtLogHandler
- setup_qt_logging
- QtAsyncWorker
- run_async_task
- async_to_qt
- BaseMainWindow
- BaseDialog
- TypedSignal
- BoundTypedSignal
- qt_slot
- bind_qt_signals
- AutoBindMixin




