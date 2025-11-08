# Справочник API

В этом разделе находится документация, автоматически сгенерированная из исходного кода `chutils`.

## Пакет `chutils`

::: chutils
    options:
      members: [init]
## Модуль `config`

::: chutils.config
    options:
      members:
        - get_config
        - get_config_value
        - get_config_int
        - get_config_float
        - get_config_boolean
        - get_config_list
        - get_config_section
        - save_config_value

### Переопределение конфигурации локальным файлом

Функция `get_config()` теперь автоматически ищет и загружает локальный файл конфигурации (например, `config.local.yml` или `config.local.ini`) в той же директории, что и основной файл (`config.yml` или `config.ini`). Значения из локального файла **переопределяют** соответствующие значения из основного файла.

Это позволяет удобно управлять чувствительными или специфичными для разработчика настройками, не коммитя их в репозиторий.

**Пример:**

Если `config.yml` содержит:
```yaml
# config.yml
Database:
  host: production_db.com
  port: 5432
App:
  debug: false
```
А `config.local.yml` содержит:
```yaml
# config.local.yml
Database:
  host: localhost
App:
  debug: true
  developer_mode: true
```
Тогда `get_config()` вернет объединенную конфигурацию, где локальные настройки переопределяют основные:
```python
{
  "Database": {
    "host": "localhost", # Переопределено локальным файлом
    "port": 5432         # Взято из основного файла
  },
  "App": {
    "debug": True,           # Переопределено локальным файлом
    "developer_mode": True   # Добавлено из локального файла
  }
}
```
**Важно:** Убедитесь, что вы добавили `config.local.yml` (или `config.local.ini`) в ваш `.gitignore`, чтобы случайно
не закоммитить локальные или чувствительные настройки.

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
