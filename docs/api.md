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

### Пример создания нескольких логгеров

Вы можете создавать разные логгеры для разных частей вашего приложения, передавая уникальное имя в `setup_logger`. Это
помогает фильтровать и разделять логи.

```python
# main.py
from chutils import setup_logger

# Основной логгер приложения
main_logger = setup_logger("main_app")
# Логгер для модуля, отвечающего за работу с базой данных
db_logger = setup_logger("database")

main_logger.info("Приложение запущено.")
db_logger.debug("Инициализация подключения к БД...")
```
В лог-файле вы увидите сообщения от обоих логгеров с указанием их имени.
Более подробный пример можно найти в файле `examples/05_different_log_levels.py`.

## Модуль `secret_manager`

::: chutils.secret_manager
