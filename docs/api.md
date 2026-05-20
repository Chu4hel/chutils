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

## Декораторы

::: chutils.decorators
options:
members:

- retry
- log_function_details
- timeout

## Исключения

::: chutils.exceptions
