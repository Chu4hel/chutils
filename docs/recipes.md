# Рецепты и полезные советы

В этом разделе собраны практические примеры решения типичных задач с помощью **chutils**.

## 1. Логирование

### Асинхронное логирование (Performance)

Для высоконагруженных приложений запись логов в файл или консоль может стать «бутылочным горлышком». Включите
асинхронный режим, чтобы вынести запись в фоновый поток.

```python
from chutils import setup_logger

# Включение асинхронного режима
logger = setup_logger(use_async=True)

# Теперь основной поток не будет ждать завершения записи на диск
logger.info("Это сообщение будет обработано в фоновом потоке")
```

### Расширенное маскирование PII

`chutils` может автоматически скрывать чувствительные данные (email, карты) не только по конкретным значениям, но и по
паттернам.

```python
from chutils import setup_logger

# Настройка автоматического маскирования email и телефонов
logger = setup_logger(
    use_predefined_patterns=["email", "phone"],
    custom_patterns=[r"ID-\d{4}"]  # Свои регулярные выражения
)

# Выведет: "Contact user [MASKED] at [MASKED]"
logger.info("Contact user ID-1234 at test@example.com")
```

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

## 2. Кэширование (Smart Caching)

Используйте декоратор `@cache_with_ttl` для автоматического сохранения результатов тяжелых функций. Он поддерживает как
обычные функции, так и асинхронные корутины.

### Как это работает

Кэширование **строго привязано к аргументам функции**. При каждом вызове декоратор генерирует уникальный ключ на основе:

1. Полного имени функции (включая модуль).
2. Всех позиционных аргументов (`args`).
3. Всех именованных аргументов (`kwargs`).

Это значит, что вызовы с разными данными будут кэшироваться независимо:

```python
@cache_with_ttl(ttl=60)
def calculate_price(item_id: int, discount: float = 0.0):
    # Вычисления...
    return final_price


# Разные аргументы = разные записи в кэше
calculate_price(1)  # Вычислится и сохранится для key_1
calculate_price(2)  # Вычислится и сохранится для key_2
calculate_price(1, 0.1)  # Вычислится и сохранится для key_3
calculate_price(1)  # Вернется из кэша (мгновенно)
```

### Примеры использования

```python
import asyncio

from chutils.cache import cache_with_ttl


# Кэшируем результат на 60 секунд
@cache_with_ttl(ttl=60)
def get_heavy_data(user_id: int):
    print(f"Вычисляем данные для {user_id}...")
    return {"id": user_id, "data": "..."}


# Асинхронный кэш с префиксом ключа
@cache_with_ttl(ttl=300, key_prefix="api_response")
async def fetch_remote_api(url: str):
    await asyncio.sleep(1)  # Имитация задержки
    return {"url": url, "status": "ok"}
```

### Основные возможности

Декоратор обладает встроенной защитой от **Cache Stampede**: если несколько потоков или тасок одновременно вызовут
функцию с одним и тем же ключом, реальное вычисление выполнит только первый, а остальные дождутся его результата и
возьмут его из кэша.

## 3. Работа с конфигурацией

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

### Специфичные для окружения конфигурации

Вы можете создавать отдельные файлы настроек для разных сред развертывания (например, `staging`, `production`).
Библиотека автоматически подхватит нужный файл на основе переменной окружения `CH_ENV`.

1. Создайте файл `config.production.yml`.
2. Установите `CH_ENV=production` в вашей среде.

**Приоритет загрузки (от высшего к низшему):**

1. Переменные окружения (`CH_SECTION_KEY`).
2. Локальный файл (`config.local.yml`).
3. Файл окружения (`config.{CH_ENV}.yml`).
4. Основной файл (`config.yml`).

## 4. Управление секретами

### Использование в Docker / CI-CD

В изолированных средах системное хранилище (Keyring) часто недоступно. Чтобы избежать лишних предупреждений и ошибок:

1. Установите переменную окружения `CH_DISABLE_KEYRING_WARNING=true`.
2. Используйте `.env` файл для хранения секретов.

```dotenv
# .env
DB_PASSWORD="my-safe-password"
```

`SecretManager` автоматически подхватит это значение.

## 5. Hot-Reload конфигурации

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

При каждом изменении файла кэш `get_config()` сбрасывается, поэтому вы всегда будете получать свежую провалидированную
модель.

```python
def on_reload():
    # При вызове заново будет создана новая модель с актуальными данными
    cfg = get_config(model=AppConfig)
    print(f"Новое имя приложения: {cfg.name}")
```

## 6. Декораторы

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

## 7. Валидация через Pydantic

### Строгая типизация всей конфигурации

Вы можете описать ожидаемую структуру вашего `config.yml` в виде Pydantic моделей для автоматической валидации при
загрузке.

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

### Интеграция с IDE (VSCode, PyCharm) через JSON Schema

Чтобы получить автодополнение и проверку типов прямо в YAML файле, вы можете сгенерировать JSON Schema для вашей
Pydantic модели и подключить её.

1. **Генерация схемы:**
   ```bash
   chutils config generate-schema --model my_app.models:Settings -o .config.schema.json
   ```

2. **Подключение в VSCode:**
   Добавьте "магический комментарий" в начало вашего `config.yml`:
   ```yaml
   # yaml-language-server: $schema=./.config.schema.json
   
   Database:
     host: localhost
     port: 5432
   ```
   *Требуется расширение "YAML" от Red Hat.*

3. **Подключение в PyCharm:**
    - Перейдите в `Settings` -> `Languages & Frameworks` -> `Schemas and DTDs` -> `JSON Schema Mappings`.
    - Добавьте новую схему, укажите путь к `.config.schema.json` и выберите ваш файл `config.yml`.

## 8. Утилита командной строки (CLI)

### Управление секретами без кода

Используйте команду `chutils`, чтобы быстро настроить секреты в окружении разработки или на сервере.

```bash
# Сохранить API ключ
chutils secrets set STRIPE_KEY "sk_test_..."

# Удалить секрет
chutils secrets delete STRIPE_KEY

# Указать конкретный сервис (по умолчанию - имя текущей папки)
chutils secrets set AWS_SECRET "..." --service my-production-app
```

## 9. Работа с файловой системой

### Безопасная запись данных

Используйте `atomic_write`, чтобы гарантировать, что файл не будет поврежден при сбое питания или внезапной остановке
процесса. Данные сначала записываются во временный файл, который затем атомарно заменяет целевой.

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

## 10. Graceful Shutdown (Управление жизненным циклом)

Механизм корректного завершения работы приложения позволяет выполнить необходимые действия по очистке ресурсов (закрытие
соединений с БД, логов, сокетов) при получении сигналов от ОС (например, `Ctrl+C`).

### Регистрация функций очистки

Используйте декоратор `@register_cleanup` для регистрации как синхронных, так и асинхронных функций.

```python
import asyncio
from chutils import register_cleanup, setup_graceful_shutdown


@register_cleanup
async def close_db():
    print("Closing database connections...")
    await asyncio.sleep(0.1)  # Имитация работы
    print("DB connections closed.")


@register_cleanup
def cleanup_temp_files():
    print("Deleting temporary files...")


# В начале работы приложения активируйте перехват сигналов
setup_graceful_shutdown()


# Пример работы асинхронного цикла
async def main():
    print("App is running... Press Ctrl+C to stop.")
    while True:
        await asyncio.sleep(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
```

### Настройка таймаута

По умолчанию на выполнение всех функций очистки дается 10 секунд. Вы можете изменить это значение в `config.yml`:

```yaml
# config.yml
shutdown:
  timeout: 5 # Таймаут в секундах
```

### Особенности работы

1. **LIFO (Last-In-First-Out):** Функции выполняются в обратном порядке их регистрации. Это удобно, если ресурсы зависят
   друг от друга (например, сначала закрыть логгер, потом БД).
2. **Log and Continue:** Если одна из функций выбросит исключение, `chutils` залогирует ошибку и продолжит выполнение
   остальных функций.
3. **Кроссплатформенность:** На Windows перехватываются `SIGINT` и `SIGTERM`, на Linux/Unix дополнительно `SIGHUP`.

## 11. Работа со временем (Painless Datetime)

Модуль `chutils.time` обеспечивает "UTC-first" подход, гарантируя, что вы всегда работаете с осведомленными (timezone
aware) объектами времени.

### Получение текущего времени в UTC

```python
from chutils import utc_now

# Возвращает datetime с tzinfo=timezone.utc
now = utc_now()
print(f"Текущее время: {now}")
```

### Умный парсинг дат

Функция `parse_datetime` поддерживает ISO строки, UNIX-таймстампы (в секундах и миллисекундах) и автоматически приводит
их к UTC.

```python
from chutils import parse_datetime

# ISO 8601
dt1 = parse_datetime("2023-10-27T12:00:00")

# UNIX Timestamp (секунды)
dt2 = parse_datetime(1698400000)

# UNIX Timestamp (миллисекунды)
dt3 = parse_datetime(1698400000000)

# Если установлена библиотека chutils[date], поддерживается любой формат:
# dt4 = parse_datetime("27 Oct 2023 12:00")
```

### Человекочитаемая разница во времени

Превращает разницу между датами в понятные строки на русском или английском языке.

```python
from datetime import timedelta
from chutils import utc_now, humanize_timedelta

now = utc_now()
past_date = now - timedelta(minutes=5)
future_date = now + timedelta(days=1)

print(humanize_timedelta(past_date))  # "5 минут назад"
print(humanize_timedelta(future_date))  # "завтра"
print(humanize_timedelta(past_date, locale='en'))  # "5 minutes ago"
```

## 12. Быстрое создание CLI (CLI Booster)

Декоратор `@cli_command` позволяет превратить любую функцию в полноценный CLI-инструмент за одну секунду. Он
автоматически создает парсер аргументов на основе сигнатуры функции.

### Простой скрипт

```python
# my_tool.py
from pathlib import Path

from chutils import cli_command


@cli_command
def copy_files(source: Path, dest: Path, verbose: bool = False):
    """
    Утилита для копирования файлов.
 
    Args:
        source (Path): Путь к исходному файлу.
        dest (Path): Путь назначения.
        verbose (bool): Выводить подробную информацию.
    """
    if verbose:
        print(f"Копируем из {source} в {dest}")
    # Логика...


if __name__ == "__main__":
    copy_files()
```

Теперь вы можете запустить его из терминала:

```bash
python my_tool.py /tmp/src /tmp/dst --verbose
python my_tool.py --help
```

### Асинхронные команды и списки

`CLI Booster` отлично справляется с асинхронностью и списками аргументов.

```python
import asyncio
from chutils import cli_command


@cli_command
async def process_batch(ids: list[int], retry: int = 3):
    """Обработка списка ID с повторами."""
    for item_id in ids:
        print(f"Processing {item_id} (retries: {retry})")
        await asyncio.sleep(0.1)


if __name__ == "__main__":
    process_batch()
```

## 13. Отладка и диагностика конфигурации (Config Diagnostics)

Если вы не понимаете, почему значение ключа в приложении отличается от того, что написано в `config.yml`, используйте
интерактивный отладчик.

### Использование через CLI

Команда `config debug` покажет всю историю изменений для каждого ключа: откуда он был загружен изначально и чем перекрыт
позже.

```bash
# Показать дерево конфигурации (по умолчанию)
chutils config debug

# Вывод в виде таблицы
chutils config debug --format table

# Показать секретные значения (по умолчанию они маскируются)
chutils config debug --show-secrets

# Экспорт в JSON для анализа
chutils config debug --format json > config_trace.json
```

### Использование через API

Вы можете включить трассировку и получить данные программно:

```python
from chutils.config.manager import _cm
from chutils.config import get_config
from chutils.config.diagnostics import format_trace

# 1. Включаем сбор метаданных
_cm.tracing_enabled = True

# 2. Сбрасываем кэш и загружаем конфиг
_cm.clear_cache()
get_config()

# 3. Получаем и форматируем отчет
trace = _cm.get_trace()
print(format_trace(trace, format_type='tree'))
```

## 14. Распределенное трассирование (OpenTelemetry)

`chutils` предоставляет легковесную интеграцию с OpenTelemetry для отслеживания пути выполнения запросов и связи логов с
трассами.

### Установка

Функционал трассировки является опциональным:

```bash
pip install chutils[otel]
```

### Быстрый старт

1. Настройте сбор трасс в начале вашего приложения:

```python
from chutils import setup_tracing

# Настройка вывода трасс в консоль (для локальной разработки)
setup_tracing(service_name="my_service", exporter_type="console")
```

2. Используйте декоратор `@trace` для функций, которые хотите отслеживать:

```python
from chutils import trace, setup_logger

logger = setup_logger()


@trace(capture_kwargs=True)
def process_order(order_id: int):
    logger.info("Начинаем обработку заказа")
    # ... логика ...
    return True
```

### Особенности

- **Связь с логами:** В текстовых логах автоматически появятся `[trace_id=... span_id=...]`. В JSON логах эти поля будут
  вынесены на верхний уровень.
- **Async:** Декоратор `@trace` полностью поддерживает асинхронные функции.
- **OTLP:** Для промышленного использования (Jaeger, Grafana Tempo) используйте `exporter_type="otlp"`.
- **Zero Overhead:** Если пакеты `opentelemetry` не установлены, декоратор `@trace` не создает никаких накладных
  расходов.

## 15. Дистанционная конфигурация (Remote Config)

`chutils` позволяет загружать настройки из удаленных HTTP/HTTPS источников. Это полезно для централизованного управления
конфигурациями в микросервисной архитектуре.

### Быстрый старт

Просто укажите URL при получении конфигурации:

```python
from chutils import get_config

# Загрузка и объединение с локальными файлами
config = get_config(remote_url="https://api.example.com/config.json")
```

### Периодический опрос (Polling)

Вы можете настроить автоматическое фоновое обновление конфигурации:

```python
# Опрос каждые 60 секунд
config = get_config(
    remote_url="https://api.example.com/config.json",
    polling_interval=60
)
```

### Динамический интервал

Вы можете управлять интервалом опроса прямо из удаленного конфига. Если в загруженных данных есть секция
`RemoteConfig` (или `polling`) с ключом `interval`, `chutils` автоматически переключится на этот интервал.

```json
{
  "RemoteConfig": {
    "interval": 300
  },
  "Database": {
    "host": "remote-db"
  }
}
```

### Авторизация и безопасность

Для доступа к защищенным эндпоинтам используйте `remote_auth`:

```python
config = get_config(
    remote_url="https://secure-config.local/app.yml",
    remote_auth=("admin", "secret-token")
)
```

### Отказоустойчивость (Fallback)

Если удаленный сервер временно недоступен, `chutils` автоматически вернет последнюю успешно загруженную версию из
памяти (кэша), чтобы приложение продолжало работать.

## 16. Инструменты разработчика и AI-контекст

Если вы хотите быстро создать документацию по API вашего проекта или подготовить глубокий индекс для AI-агента.

### Генерация карты API

Создает Markdown-файл со списком всех публичных функций, классов и их описаний.

```bash
chutils dev generate-context -o api_map.md
```

### Генерация семантического индекса для AI

Генерирует JSON-дерево проекта (через AST), которое включает связи между модулями, веса зависимостей и метаданные символов. Это "золотой стандарт" контекста для современных LLM.

```bash
chutils dev generate-context --tree -o project_index.json
```