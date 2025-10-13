# chutils

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT) [![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)

Набор простых и удобных утилит для Python, который избавляет от рутины при работе с конфигурацией, логированием и секретами в новых проектах.

## Проблема

Каждый раз, начиная новый проект, приходится решать одни и те же задачи:
- Как удобно читать настройки из файла `config.ini`?
- Как настроить логирование, чтобы сообщения писались и в консоль, и в файл с ежедневной ротацией?
- Как безопасно хранить API-ключи, пароли и другие секреты, не записывая их в код или в `config.ini`?
- Как сделать так, чтобы все это работало без жестко прописанных путей сразу после установки?

**chutils** решает эти проблемы.

## Ключевые возможности

- **✨ Ноль конфигурации:** Библиотека **автоматически** находит корень вашего проекта и файл `config.ini`. Вам не нужно ничего инициализировать вручную.
- **⚙️ Удобная работа с конфигом:** Простые функции для получения строковых, числовых, булевых значений и даже списков из `config.ini`.
- **✍️ Продвинутый логгер:** Функция `setup_logger()` "из коробки" настраивает логирование в консоль и в ротируемые файлы. Возвращает кастомный логгер с дополнительными уровнями отладки (`devdebug`, `mediumdebug`).
- **🔒 Безопасное хранилище секретов:** Модуль `secret_manager` предоставляет простой интерфейс для сохранения и получения секретов через системное хранилище ключей (Keyring), такое как Windows Credential Manager, macOS Keychain или Secret Service в Linux.
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

## Быстрый старт

1.  Создайте в корне вашего проекта файл `config.ini`.

    **Структура проекта:**
    ```
    my_awesome_app/
    ├── main.py
    └── config.ini
    ```

    **Содержимое `config.ini`:**
    ```ini
    [API]
    base_url = https://api.example.com

    [Database]
    host = localhost
    port = 5432
    user = my_user
    ```

2.  Используйте `chutils` в вашем коде `main.py`:

    ```python
    # main.py
    from chutils.config import get_config_value
    from chutils.logger import setup_logger, ChutilsLogger
    from chutils.secret_manager import SecretManager

    # 1. Настраиваем логгер. Он автоматически прочитает настройки из config.ini.
    logger: ChutilsLogger = setup_logger()

    # 2. Инициализируем менеджер секретов для нашего приложения.
    #    Секреты будут храниться изолированно под именем "my_awesome_app".
    secrets = SecretManager("my_awesome_app")

    def setup_credentials():
        """Функция для первоначального сохранения пароля."""
        db_user = get_config_value("Database", "user")
        if not secrets.get_secret(f"{db_user}_password"):
            logger.info("Пароль для БД не найден. Сохраняем новый пароль...")
            secrets.save_secret(f"{db_user}_password", "MySuperSecretDbPassword123!")
            logger.info("Пароль для БД сохранен в системном хранилище.")

    def connect_to_db():
        # 3. Легко получаем значения из конфига и секреты из хранилища.
        db_host = get_config_value("Database", "host")
        db_user = get_config_value("Database", "user")
        db_password = secrets.get_secret(f"{db_user}_password")

        if not db_password:
            logger.error("Не удалось получить пароль для БД!")
            return

        logger.info(f"Подключаемся к базе данных по адресу {db_host} от имени {db_user}...")
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

3.  Запустите ваш скрипт. Вы увидите логи в консоли, а в проекте появится папка `logs` с файлом лога. Пароль от БД будет надежно сохранен в системном хранилище.

## API и Использование

### Работа с конфигурацией (`chutils.config`)

- `get_config_value(section, key, fallback="")`: Получить строковое значение.
- `get_config_int(section, key, fallback=0)`: Получить целое число.
- `get_config_boolean(section, key, fallback=False)`: Получить булево значение.
- `get_config_list(section, key, fallback=[])`: Получить список строк из многострочного значения.
- `get_config_section(section)`: Получить всю секцию как словарь.
- `save_config_value(section, key, value)`: Сохранить значение в `config.ini`, сохраняя комментарии.

### Настройка логирования (`chutils.logger`)

- `setup_logger(name='app_logger', log_level_str='')`: Настраивает и возвращает экземпляр `ChutilsLogger`.
- `logger.mediumdebug("message")`: Логирование с уровнем 15, промежуточным между `DEBUG` и `INFO`.
- `logger.devdebug("message")`: Логирование с уровнем 9, для очень подробной отладки.

### Управление секретами (`chutils.secret_manager`)

- `SecretManager(service_name)`: Создает менеджер, изолированный по имени сервиса (вашего приложения).
- `secrets.save_secret(key, value)`: Сохраняет секрет.
- `secrets.get_secret(key)`: Получает секрет. Возвращает `None`, если не найден.
- `secrets.delete_secret(key)`: Удаляет секрет.

### Ручная инициализация (`chutils.init`)

В 99% случаев вам это **не понадобится**. Но если автоматика не справилась, вы можете один раз указать путь к проекту вручную:
```python
import chutils
chutils.init(base_dir="/path/to/my/project/root")
```

### Пример файла `config.ini`

`chutils` использует секцию `[Logging]` для настройки логгера.

```ini
[API]
token = your_secret_token_here

[Database]
host = localhost

[Logging]
# Уровни: DEVDEBUG, DEBUG, MEDIUMDEBUG, INFO, WARNING, ERROR, CRITICAL
log_level = DEBUG
# Имя файла для логов
log_file_name = my_app.log
# Сколько дней хранить файлы логов
log_backup_count = 7
```

## Лицензия

Проект распространяется под лицензией MIT.
