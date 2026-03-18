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

- **✨ Ноль конфигурации:** Библиотека **автоматически** находит корень вашего проекта и файл `config.yml` или
  `config.ini`. Если файл не найден, используются безопасные настройки по умолчанию (например, логирование только в
  консоль).
- **⚙️ Гибкая конфигурация:** Поддержка `YAML` и `INI` форматов. Простые функции для получения типизированных данных.
- **✍️ Продвинутый логгер:** Функция `setup_logger()` "из коробки" настраивает логирование в консоль и в ротируемые
  файлы. Возвращает кастомный логгер с дополнительными уровнями отладки (`devdebug`, `mediumdebug`).
- **🔒 Безопасное хранилище секретов:** Модуль `secret_manager` предоставляет простой интерфейс для сохранения и
  получения секретов. Поддерживает системное хранилище `keyring` и может использовать `.env` файлы как запасной вариант.
- **🚀 Готовность к работе:** Просто установите и используйте.

## Установка

```bash
poetry add chutils
```

Или с помощью pip:

```bash
pip install chutils
```

Для разработки клонируйте репозиторий и установите его в режиме редактирования:

```bash
git clone https://github.com/Chu4hel/chutils.git
cd chutils
pip install -e .
```

## Примеры использования

В папке [`/examples`](../examples/) вы найдете готовые к запуску скрипты, демонстрирующие ключевые возможности
библиотеки. Каждый пример сфокусирован на одной конкретной задаче.

## Быстрый старт

### 1. Работа с конфигурацией

1. (Опционально) Создайте файл `config.yml` в корне вашего проекта. Если этого не сделать, библиотека будет использовать
   настройки по умолчанию:

   ```yaml
   # config.yml
   Database:
     host: localhost
     port: 5432
     user: my_user
   ```

2. Получайте значения в вашем коде:

   ```python
   # main.py
   from chutils import get_config_value, get_config_int

   db_host = get_config_value("Database", "host", fallback="127.0.0.1")
   db_port = get_config_int("Database", "port", fallback=5433)

   print(f"Подключаемся к БД по адресу: {db_host}:{db_port}")
   # Вывод: Подключаемся к БД по адресу: localhost:5432
   ```
   `chutils` автоматически найдет `config.yml` и прочитает из него данные.

   #### Переопределение конфигурации локальным файлом (`config.local.yml`)

   Вы можете создать локальный файл конфигурации (например, `config.local.yml` или `config.local.ini`) рядом с основным
   файлом (`config.yml` или `config.ini`). Значения из локального файла будут **переопределять** соответствующие
   значения из основного файла. Это удобно для:
    - Хранения чувствительных данных, которые не должны попадать в систему контроля версий (добавьте `config.local.yml`
      в `.gitignore`).
    - Переопределения настроек для локальной разработки без изменения основного файла.

   Пример:
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
   Тогда `get_config()` вернет:
   ```yaml
   Database:
     host: localhost # Переопределено локальным файлом
     port: 5432      # Взято из основного файла
   App:
     debug: true         # Переопределено локальным файлом
     developer_mode: true # Добавлено из локального файла
   ```
   **Важно:** Убедитесь, что вы добавили `config.local.yml` (или `config.local.ini`) в ваш `.gitignore`, чтобы случайно
   не закоммитить локальные или чувствительные настройки.

### 2. Настройка логирования

1. Добавьте секцию `Logging` в ваш `config.yml` (опционально):

   ```yaml
   # config.yml
   Logging:
     log_level: DEBUG
     log_file_name: my_app.log
   ```

2. Используйте логгер:

   ```python
   # main.py
   from chutils import setup_logger, ChutilsLogger

   # Настраиваем логгер. Он сам прочитает настройки из конфига.
   logger: ChutilsLogger = setup_logger()

   logger.info("Приложение запущено.")
   logger.debug("Это отладочное сообщение.")
   # Вывод в консоли и запись в файл logs/my_app.log
   ```
   Папка `logs` будет создана автоматически.

   Вы также можете указать имя файла лога напрямую при вызове `setup_logger`, переопределив значение из конфигурации:
   ```python
   # main.py
   from chutils import setup_logger, ChutilsLogger

   # Логгер будет писать в custom.log, игнорируя log_file_name из config.yml
   logger: ChutilsLogger = setup_logger(log_file_name="custom.log")

   logger.info("Сообщение в кастомном файле.")
   ```

   #### Управление логированием через переменные окружения

   Вы можете управлять поведением логирования глобально с помощью переменных окружения. Это особенно полезно для
   облачных сред (Docker, Serverless).

    - `CH_LOG_NO_TIME=true`: Удаляет дату и время из формата логов.
    - `CH_LOG_NO_FILE=true`: Полностью отключает создание файлов логов, даже если они настроены в коде или `config.yml`.

   Эти переменные имеют **высший приоритет** и переопределяют любые параметры, переданные в `setup_logger()`.

   #### Создание нескольких логгеров

   Вы можете создавать разные логгеры для разных частей вашего приложения, передавая уникальное имя в `setup_logger`.
   Это
   помогает фильтровать и разделять логи.

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
   Более подробный пример можно найти в [`/examples/05_different_log_levels.py`](./examples/05_different_log_levels.py).

   #### Конфигурация нескольких логгеров через файл

   Вы можете централизованно управлять настройками разных логгеров, используя параметр `config_section_name`.

    1. **Добавьте секции в `config.yml`**:
       Секция `[Logging]` используется для настроек по умолчанию. Остальные секции можно использовать для специфичных
       логгеров.
       ```yaml
       # config.yml
       Logging:
         log_level: INFO
         rotation_type: time
         compress: true
 
       AuditLogger:
         log_level: DEBUG
         log_file_name: "audit.log"
       ```

    2. **Используйте `config_section_name` в коде**:
       ```python
       # main.py
       from chutils import setup_logger
 
       # Этот логгер возьмет настройки из секции [Logging]
       main_logger = setup_logger("main")
       main_logger.info("Сообщение от основного логгера.")
 
       # А этот логгер - из секции [AuditLogger], которая переопределит настройки из [Logging]
       audit_logger = setup_logger("audit", config_section_name="AuditLogger")
       audit_logger.debug("Детальное сообщение для аудита.")
       ```

### 3. Управление секретами

`SecretManager` ищет секреты в следующем порядке:

1. **Системное хранилище (`keyring`)**: Наиболее безопасный способ.
2. **Файл `.env`**: Если секрет не найден в `keyring`, менеджер будет искать его в файле `.env` в корне вашего проекта.
3. **Переменные окружения**: Если секрета нет и там, будет произведен поиск в переменных окружения ОС.

#### Способ 1: Keyring (рекомендуемый)

1. Инициализируйте `SecretManager` и сохраните ваш секрет. **Это нужно сделать один раз.**

   ```python
   # setup_secrets.py
   from chutils import SecretManager

   secrets = SecretManager("my_awesome_app")
   secrets.save_secret("DB_PASSWORD", "MySuperSecretDbPassword123!")
   print("Пароль от БД сохранен в системном хранилище!")
   ```

2. Получайте секрет в основном коде, не "светя" им:

   ```python
   # main.py
   from chutils import SecretManager, get_config_value

   secrets = SecretManager("my_awesome_app")
   db_user = get_config_value("Database", "user")

   # Получаем пароль из безопасного хранилища
   db_password = secrets.get_secret("DB_PASSWORD")

   if db_password:
       print(f"Получен пароль для пользователя {db_user}.")
   else:
       print("Пароль не найден!")
   ```

#### Способ 2: Файл .env (удобно для Docker и CI/CD)

1. Создайте файл `.env` в корне вашего проекта:
   ```dotenv
   # .env
   DB_PASSWORD="AnotherSecretPassword"
   API_KEY="abcdef123456"
   ```

2. `SecretManager` автоматически найдет этот файл и прочитает из него переменные, если не найдет их в `keyring`.

   ```python
   # main.py
   from chutils import SecretManager

   secrets = SecretManager("my_awesome_app")

   # Этот секрет будет взят из .env, если его нет в keyring
   api_key = secrets.get_secret("API_KEY")
   print(f"Найден API ключ: {api_key}")
   ```

#### Отключение Keyring и подавление предупреждений (Опционально)

В средах, где `keyring` недоступен (например, Docker, CI/CD), вы можете явно отключить его использование и подавить
соответствующие предупреждения, если вы предпочитаете чистый вывод и планируете использовать только `.env` файлы или
переменные окружения. Это чисто опциональная настройка для вашего удобства.

**Способ 1: Переменная окружения**
Установите `CH_DISABLE_KEYRING_WARNING=true` (или `1`) в окружении ОС.

**Способ 2: Файл конфигурации**
Добавьте в ваш `config.yml`:

```yaml
secrets:
  disable_keyring: true
```

Если опция включена, `SecretManager` будет пропускать проверку `keyring` и сразу искать секреты в `.env` и переменных
окружения.

## Комплексный пример

Этот пример показывает, как все компоненты `chutils` работают вместе.

1. **Файл `config.yml`:**
   ```yaml
   API:
     base_url: https://api.example.com

   Database:
     host: localhost
     port: 5432
     user: my_user

   Logging:
     log_level: INFO
   ```

2. **Код `main.py`:**
   ```python
   # main.py
   from chutils import get_config_value, setup_logger, SecretManager, ChutilsLogger

   # 1. Настраиваем логгер. Он автоматически прочитает настройки из конфига.
   logger: ChutilsLogger = setup_logger()

   # 2. Инициализируем менеджер секретов для нашего приложения.
   secrets = SecretManager("my_awesome_app")

   def setup_credentials():
       """Функция для первоначального сохранения пароля, если его нет."""
       db_user = get_config_value("Database", "user")
       password_key = f"{db_user}_password"

       if not secrets.get_secret(password_key):
           logger.info("Пароль для БД не найден. Сохраняем новый...")
           secrets.save_secret(password_key, "MySuperSecretDbPassword123!")
           logger.info("Пароль для БД сохранен в системном хранилище.")

   def connect_to_db():
       """Пример подключения к БД с использованием конфига и секретов."""
       db_host = get_config_value("Database", "host")
       db_user = get_config_value("Database", "user")
       db_password = secrets.get_secret(f"{db_user}_password")

       if not db_password:
           logger.error("Не удалось получить пароль для БД!")
           return

       logger.info(f"Подключаемся к {db_host} от имени {db_user}...")
       # ... логика подключения ...
       logger.info("Успешно подключились!")

   def main():
       logger.info("Приложение запущено.")
       setup_credentials()
       connect_to_db()
       logger.info("Приложение завершило работу.")

   if __name__ == "__main__":
       main()
   ```

## API

### Работа с конфигурацией (`chutils.config`)

- `get_config_value(section, key, fallback="")`: Получить значение.
- `get_config_int(section, key, fallback=0)`: Получить целое число.
- `get_config_boolean(section, key, fallback=False)`: Получить булево значение.
- `get_config_list(section, key, fallback=[])`: Получить список.
- `get_config_section(section)`: Получить всю секцию как словарь.
- `save_config_value(section, key, value)`: Сохранить значение. Работает для `.yml` и `.ini`.
  **Важно**: при сохранении в `.yml` комментарии и форматирование будут утеряны. При сохранении в `.ini` - сохраняются.

### Настройка логирования (`chutils.logger`)

- `setup_logger(name='app_logger', log_level_str='')`: Настраивает и возвращает экземпляр `ChutilsLogger`.
- `logger.mediumdebug("message")`: Логирование с уровнем 15. Промежуточный уровень между `DEBUG` и `INFO`.
- `logger.devdebug("message")`: Логирование с уровнем 9. Самый подробный уровень для глубокой отладки (например, для
  вывода дампов переменных).

### Управление секретами (`chutils.secret_manager`)

- `SecretManager(service_name, prefix="Chutils_")`: Создает менеджер, изолированный по имени сервиса.
- `secrets.save_secret(key, value)`: Сохраняет секрет.
- `secrets.get_secret(key)`: Получает секрет.
- `secrets.delete_secret(key)`: Удаляет секрет.

### Декораторы (`chutils.decorators`)

- `log_function_details`: Декоратор для логирования деталей вызова функции (аргументы, время выполнения, результат).

### Ручная инициализация (`chutils.init`)

В 99% случаев вам это **не понадобится**. Но если автоматика не справилась, вы можете один раз указать путь к проекту
вручную в самом начале работы приложения:

```python
import chutils

chutils.init(base_dir="/path/to/my/project/root")
```

### Особенности `secret_manager` (Keyring)

Модуль `SecretManager` использует библиотеку `keyring` для безопасного хранения секретов в системном хранилище.

- На **Windows** и **macOS** это работает "из коробки".
- **Требования для Linux**: На Linux для безопасной работы `keyring` требуется установленный и настроенный "бэкенд"
  (хранилище секретов), например, `GNOME Keyring` (Seahorse) или `KWallet`. На серверах или минималистичных сборках его
  может понадобиться установить вручную.
  Подробнее — в [официальной документации `keyring`](https://keyring.readthedocs.io/en/latest/).
- **Использование на мобильных ОС**: Этот модуль **не предназначен** для использования на мобильных операционных
  системах (Android, iOS). `keyring` с высокой вероятностью не найдет системного хранилища и будет использовать
  **незащищенный** способ хранения ваших секретов.

## Лицензия

Проект распространяется под лицензией MIT.
