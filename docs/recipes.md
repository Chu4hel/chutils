# Рецепты и полезные советы

В этом разделе собраны практические примеры решения типичных задач с помощью **chutils**.

## 1. Логирование

### Несколько логгеров для разных модулей

Если ваше приложение состоит из нескольких крупных компонентов, удобно разделять их логи.

```python
from chutils import setup_logger

# Логгер для сетевого модуля (только ошибки в файл network.log)
net_logger = setup_logger("network", log_level="ERROR", log_file_name="network.log")

# Логгер для ядра (детальная отладка в консоль и core.log)
core_logger = setup_logger("core", log_level="DEVDEBUG", log_file_name="core.log")

net_logger.error("Ошибка соединения!")
core_logger.devdebug("Состояние объекта: %s", obj_data)
```

### Настройка через конфигурационный файл

Вы можете централизованно управлять всеми логгерами в `config.yml`:

```yaml
# config.yml
Logging:
  log_level: INFO
  rotation_type: time

AuditLogger:
  log_level: DEBUG
  log_file_name: "audit.log"
```

В коде:

```python
# Использует секцию AuditLogger
audit_logger = setup_logger("audit", config_section_name="AuditLogger")
```

## 2. Работа с конфигурацией

### Использование относительных путей

`chutils` умеет автоматически делать пути абсолютными относительно корня проекта.

```yaml
# config.yml
Paths:
  upload_dir: "data/uploads"
```

В коде:

```python
from chutils import get_config_path

# Если корень /home/user/project, вернет /home/user/project/data/uploads
upload_path = get_config_path("Paths", "upload_dir")
```

### Локальные переопределения

Создайте `config.local.yml` (и добавьте его в `.gitignore`), чтобы переопределить настройки для разработки:

```yaml
# config.local.yml
Database:
  host: "localhost" # На сервере будет production.db.com
```

## 3. Управление секретами

### Использование в Docker / CI-CD

В изолированных средах системное хранилище (Keyring) часто недоступно. Чтобы избежать лишних предупреждений и ошибок:

1. Установите переменную окружения `CH_DISABLE_KEYRING_WARNING=true`.
2. Используйте `.env` файл для хранения секретов.

```dotenv
# .env
DB_PASSWORD="my-safe-password"
```

`SecretManager` автоматически подхватит это значение.

## 4. Декораторы

### Отладка производительности

Используйте декоратор `@log_function_details` для быстрого анализа работы функций без изменения их кода.

```python
from chutils import log_function_details, setup_logger

# Важно: установите уровень DEVDEBUG, чтобы увидеть вывод декоратора
setup_logger(log_level="DEVDEBUG")


@log_function_details
def process_heavy_task(data):
    # Какая-то логика...
    return True


process_heavy_task([1, 2, 3])
```

В логах появится время выполнения с точностью до миллисекунд и переданные аргументы.
