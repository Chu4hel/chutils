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

### Ротация и сжатие логов

Функция `setup_logger` теперь поддерживает расширенные опции ротации и сжатия логов, позволяя более гибко управлять файлами логов. Эти параметры могут быть заданы как напрямую в вызове `setup_logger`, так и через конфигурационный файл `config.yml` в секции `Logging`.

**Параметры ротации:**

*   `rotation_type` (строка): Определяет тип ротации.
    *   `'time'` (по умолчанию): Ротация происходит по времени (например, ежедневно).
    *   `'size'`: Ротация происходит, когда файл лога достигает определенного размера.
*   `max_bytes` (целое число): Максимальный размер файла лога в байтах. Используется только если `rotation_type` установлен в `'size'`. При достижении этого размера файл будет ротирован. Значение `0` означает отсутствие лимита по размеру.
*   `compress` (булево): Если `True`, ротированные файлы логов будут автоматически сжиматься в формат `.gz`. Это помогает экономить место на диске.
*   `backup_count` (целое число): Количество ротированных файлов логов, которые будут храниться. Старые файлы, превышающие это количество, будут удаляться.

**Примеры использования:**

**1. Ротация по размеру со сжатием:**

Чтобы настроить логгер, который ротирует файлы при достижении 1 МБ и сжимает старые бэкапы, используйте:

```python
from chutils import setup_logger

logger = setup_logger(
    "my_app_size_rotated",
    log_file_name="app_size.log",
    rotation_type='size',
    max_bytes=1048576,  # 1 МБ
    compress=True,
    backup_count=5
)
logger.info("Это сообщение будет записано в файл app_size.log, который будет ротироваться по размеру и сжиматься.")
```

**2. Ежедневная ротация со сжатием (по умолчанию):**

Для ежедневной ротации со сжатием (это поведение по умолчанию, если `rotation_type` не указан или равен `'time'`):

```python
from chutils import setup_logger

logger = setup_logger(
    "my_app_time_rotated",
    log_file_name="app_time.log",
    rotation_type='time', # Можно опустить, так как это значение по умолчанию
    compress=True,
    backup_count=7
)
logger.info("Это сообщение будет записано в файл app_time.log, который будет ротироваться ежедневно и сжиматься.")
```

**3. Настройка через `config.yml`:**

Вы также можете управлять этими параметрами через ваш `config.yml`:

```yaml
# config.yml
Logging:
  log_level: INFO
  log_file_name: app.log
  rotation_type: size      # Или 'time'
  max_bytes: 5242880       # 5 МБ, если rotation_type: size
  compress: true           # Сжимать ротированные файлы
  log_backup_count: 10     # Хранить 10 бэкапов
```

При такой конфигурации вызов `setup_logger()` без явных параметров автоматически применит эти настройки:

```python
from chutils import setup_logger

logger = setup_logger("my_app")
logger.info("Настройки ротации и сжатия взяты из config.yml.")
```

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
