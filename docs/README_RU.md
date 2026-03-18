# chutils: Рутина — в прошлом!

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)
[![PyPI version](https://badge.fury.io/py/chutils.svg)](https://badge.fury.io/py/chutils)
[![Documentation](https://img.shields.io/badge/документация-читать-brightgreen)](https://Chu4hel.github.io/chutils/)

**chutils** — это набор простых утилит для Python, который избавляет от повторяющейся настройки конфигурации,
логирования и секретов в ваших проектах.

Начните новый проект и сразу сфокусируйтесь на главном, а не на рутине.

Полная документация доступна на [нашем сайте](https://Chu4hel.github.io/chutils/).

## Проблема

Каждый раз, начиная новый проект, приходится решать одни и те же задачи:

- Как удобно читать настройки из файла конфигурации?
- Как настроить логирование, чтобы сообщения писались и в консоль, и в файл с ежедневной ротацией?
- Как безопасно хранить API-ключи, не прописывая их в коде?
- Как сделать, чтобы всё это работало "из коробки", без прописывания путей?

**chutils** предлагает готовые решения для всех этих проблем.

## Ключевые возможности

- **✨ Ноль конфигурации:** Библиотека **автоматически** находит корень вашего проекта и файлы `config.yml` или
  `config.ini`. Используется **ленивая инициализация** — никаких тяжелых действий до реального обращения к функциям.
- **⚙️ Гибкая конфигурация:** Поддержка `YAML` и `INI` форматов. Простые функции для получения типизированных данных.
- **✍️ Продвинутый логгер:** Функция `setup_logger()` "из коробки" настраивает логирование в консоль и в ротируемые
  файлы. Возвращает кастомный логгер с дополнительными уровнями отладки (`devdebug`, `mediumdebug`).
- **🔒 Безопасное хранилище секретов:** Модуль `secret_manager` предоставляет простой интерфейс для сохранения и
  получения секретов через системный `keyring` с автоматическим откатом к `.env` файлам.
- **⚡ Поддержка Async:** Большинство функций имеют асинхронные версии (с префиксом `a`) для работы в неблокирующем
  режиме.
- **🚀 Готовность к работе:** Просто установите и используйте.

## Установка

```bash
poetry add chutils
```

Или с помощью pip:

```bash
pip install chutils
```

## Примеры использования

В папке [`/examples`](../examples/) вы найдете готовые к запуску скрипты, демонстрирующие ключевые возможности
библиотеки. Каждый пример сфокусирован на одной конкретной задаче.

## Быстрый старт

### 1. Работа с конфигурацией

1. (Опционально) Создайте файл `config.yml` в корне вашего проекта:

   ```yaml
   # config.yml
   Database:
     host: localhost
     port: 5432
   ```

2. Получайте значения в коде:

   ```python
   from chutils import get_config_value, get_config_int

   db_host = get_config_value("Database", "host", fallback="127.0.0.1")
   db_port = get_config_int("Database", "port", fallback=5432)
   ```

   #### Переопределение локальным файлом (`config.local.yml`)

   Вы можете создать `config.local.yml` рядом с основным файлом. Значения из него будут **переопределять** основные. Это
   удобно для локальной разработки или хранения секретов (не забудьте добавить `*.local.*` в `.gitignore`).

### 2. Настройка логирования

```python
from chutils import setup_logger, ChutilsLogger

# Автоматически читает настройки из секции [Logging] в config.yml
logger: ChutilsLogger = setup_logger()

logger.info("Приложение запущено.")
logger.devdebug("Очень подробное сообщение (уровень 9).")
```

#### Управление через переменные окружения

- `CH_LOG_NO_TIME=true`: Удаляет дату/время из формата (удобно для чистых логов в Docker).
- `CH_LOG_NO_FILE=true`: Полностью отключает создание файлов логов.

Переменные имеют **высший приоритет** над кодом и конфигурационным файлом.

### 3. Управление секретами

`SecretManager` ищет секреты в порядке: **Keyring > .env файл > Переменные окружения**.

```python
from chutils import SecretManager

secrets = SecretManager("my_awesome_app")

# Сохранить (один раз)
secrets.save_secret("API_KEY", "secret-value-123")

# Использовать везде
key = secrets.get_secret("API_KEY")
```

#### Отключение Keyring (Опционально)

В Docker или CI/CD, где `keyring` недоступен, можно подавить варнинги:

- Установите переменную `CH_DISABLE_KEYRING_WARNING=true`.
- Или добавьте `disable_keyring: true` в секцию `secrets` в `config.yml`.

## Обзор API

### Конфигурация (`chutils.config`)

- `get_config_value(section, key, fallback)` / `aget_config()`
- `get_config_int`, `get_config_boolean`, `get_config_list`, `get_config_path`
- `save_config_value(section, key, value)` / `asave_config_value()`

### Логирование (`chutils.logger`)

- `setup_logger(name, log_level, log_file_name, rotation_type, compress, ...)`
- Уровни: `logger.devdebug` (9), `logger.mediumdebug` (15) и стандартные.

### Секреты (`chutils.secret_manager`)

- `SecretManager(service_name, prefix)`
- `save_secret` / `asave_secret`
- `get_secret` / `aget_secret`
- `delete_secret` / `adelete_secret`

### Декораторы (`chutils.decorators`)

- `@log_function_details`: Логирует аргументы, время и результат функции (уровень `DEVDEBUG`).

## Лицензия

Проект распространяется под лицензией MIT.
