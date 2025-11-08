# Справочник API

В этом разделе находится документация, автоматически сгенерированная из исходного кода `chutils`.

## Пакет `chutils`

::: chutils
    options:
      members: [init]
## Модуль `config`

::: chutils.config

## Модуль `logger`

::: chutils.logger
    options:
      members:
        - setup_logger
        - ChutilsLogger
        - DEVDEBUG_LEVEL_NUM
        - MEDIUMDEBUG_LEVEL_NUM

### Пример создания нескольких логгеров

Вы можете создавать разные логгеры для разных частей вашего приложения, передавая уникальное имя в `setup_logger`. Параметр `log_file_name` позволяет указать отдельный файл для каждого логгера, что помогает фильтровать и разделять логи.

```python
# main.py
from chutils import setup_logger

# Основной логгер приложения будет писать в main_app.log
main_logger = setup_logger("main_app", log_file_name="main_app.log")
# Логгер для модуля, отвечающего за работу с базой данных, будет писать в database.log
db_logger = setup_logger("database", log_file_name="database.log")

main_logger.info("Приложение запущено.")
db_logger.debug("Инициализация подключения к БД...")
```
В лог-файлах вы увидите сообщения от соответствующих логгеров.
Более подробный пример можно найти в файле `examples/05_different_log_levels.py`.

## Модуль `secret_manager`

::: chutils.secret_manager
