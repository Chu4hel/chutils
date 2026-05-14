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
- get_base_dir
- get_config_file_path
- is_config_loaded

## Модуль `logger`

::: chutils.logger
options:
members:
- setup_logger
- ChutilsLogger
- DEVDEBUG_LEVEL_NUM
- MEDIUMDEBUG_LEVEL_NUM

## Модуль `secret_manager`

::: chutils.secret_manager

## Декораторы

::: chutils.decorators
options:
members:
- retry
- log_function_details
