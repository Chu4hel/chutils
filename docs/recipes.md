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

### Контекстное логирование в FastAPI / asyncio

Если вы хотите автоматически добавлять ID запроса во все логи без передачи его через аргументы функций.

```python
from chutils import setup_logger, bind_context
import asyncio

logger = setup_logger()

async def deep_nested_function():
    # Нам не нужно передавать request_id сюда, он подхватится сам!
    logger.info("Лог из глубины приложения")

async def handle_request(request_id: str):
    bind_context(request_id=request_id)
    logger.info("Начало обработки")
    await deep_nested_function()

# В асинхронном цикле контексты изолированы
asyncio.gather(
    handle_request("REQ-1"),
    handle_request("REQ-2")
)
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

## 4. Hot-Reload конфигурации

### Автоматическое обновление состояния приложения

Если ваше приложение должно менять свое поведение (например, уровень логирования или лимиты) без перезагрузки.

```python
from chutils import (
    setup_logger, 
    start_config_watcher, 
    on_config_change, 
    get_config_value
)

logger = setup_logger()

def update_app_state():
    # Читаем новые значения
    new_limit = get_config_value("App", "rate_limit", 100)
    logger.info(f"Лимит обновлен: {new_limit}")
    
    # Здесь можно обновить объект приложения или глобальное состояние
    # app.rate_limiter.set_limit(new_limit)

# 1. Подписываемся на изменения
on_config_change(update_app_state)

# 2. Запускаем мониторинг
start_config_watcher()
```

### Использование с Pydantic моделями

При каждом изменении файла кэш `get_config()` сбрасывается, поэтому вы всегда будете получать свежую провалидированную модель.

```python
def on_reload():
    # При вызове заново будет создана новая модель с актуальными данными
    cfg = get_config(model=AppConfig)
    print(f"Новое имя приложения: {cfg.name}")
```

## 5. Декораторы

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

## 5. Валидация через Pydantic

### Строгая типизация всей конфигурации

Вы можете описать ожидаемую структуру вашего `config.yml` в виде Pydantic моделей для автоматической валидации при загрузке.

```python
from pydantic import BaseModel, Field
from chutils import get_config

class DbConfig(BaseModel):
    host: str
    port: int

class AppConfig(BaseModel):
    name: str
    version: str
    db: DbConfig = Field(alias="Database")

# Валидация и автодополнение
cfg = get_config(model=AppConfig)
print(f"Подключение к {cfg.db.host}:{cfg.db.port}")
```

### Валидация отдельной секции

Если вам нужна только часть настроек:

```python
from chutils import get_config_section

db_cfg = get_config_section("Database", model=DbConfig)
```

## 6. Утилита командной строки (CLI)

### Управление секретами без кода

Используйте команду `chutils`, чтобы быстро настроить секреты в окружении разработки или на сервере.

```bash
# Сохранить API ключ
chutils secrets set STRIPE_KEY "sk_test_..."

# Удалить секрет
chutils secrets delete STRIPE_KEY

# Указать конкретный сервис (по умолчанию - имя текущей папки)
chutils secrets set AWS_SECRET "..." --service my-production-app

## 7. Работа с файловой системой

### Безопасная запись данных

Используйте `atomic_write`, чтобы гарантировать, что файл не будет поврежден при сбое питания или внезапной остановке процесса. Данные сначала записываются во временный файл, который затем атомарно заменяет целевой.

```python
from chutils.fs import atomic_write

config_data = {"version": 1, "settings": {"theme": "dark"}}

# Автоматически сериализует в JSON, так как расширение .json
atomic_write("settings.json", config_data)

# Автоматически сериализует в YAML, так как расширение .yaml
atomic_write("settings.yaml", config_data)

# Запись обычного текста
atomic_write("hello.txt", "Hello world")
```

### Временные файлы с авто-удалением

Контекстный менеджер `get_temp_file` создает временный файл и гарантированно удаляет его при выходе из блока `with`.

```python
from chutils.fs import get_temp_file

with get_temp_file(suffix=".tmp") as temp_path:
    # Делаем что-то с временным файлом
    temp_path.write_text("temporary content")
    print(f"Путь к файлу: {temp_path}")

# Здесь файл уже удален
```
