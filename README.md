# chutils

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT) [![Python](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/downloads/)

Набор простых и удобных утилит для Python, который избавляет от рутины при работе с конфигурацией и логированием в новых проектах.

## Проблема

Каждый раз, начиная новый проект, приходится решать одни и те же задачи:
- Как удобно читать настройки из файла `config.ini`?
- Как настроить логирование, чтобы сообщения писались и в консоль, и в файл с ежедневной ротацией?
- Как сделать так, чтобы это работало без жестко прописанных путей и работало сразу после установки?

**chutils** решает эти проблемы.

## Ключевые возможности

- **✨ Ноль конфигурации:** Библиотека **автоматически** находит корень вашего проекта и файл `config.ini`. Вам не нужно ничего инициализировать вручную.
- **⚙️ Удобная работа с конфигом:** Простые функции для получения строковых, числовых, булевых значений и даже списков из `config.ini`.
- **✍️ Мощный логгер:** Функция `setup_logger()` "из коробки" настраивает логирование в консоль и в ротируемые файлы в папке `logs/`, которая создается автоматически.
- **🚀 Готовность к работе:** Просто установите и используйте.

## Установка

Вы можете установить пакет напрямую из GitHub-репозитория с помощью `pip`:

```bash
pip install git+https://github.com/Chu4hel/chutils.git
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
    token = your_secret_token_here

    [Database]
    host = localhost
    port = 5432
    ```

2.  Используйте `chutils` в вашем коде `main.py`:

    ```python
    # main.py
    from chutils.config import get_config_value
    from chutils.logger import setup_logger

    # 1. Настраиваем логгер. Он автоматически прочитает настройки из config.ini
    #    и создаст папку logs/
    logger = setup_logger()

    def connect_to_db():
        # 2. Легко получаем значения из конфига
        db_host = get_config_value("Database", "host")
        db_port = get_config_value("Database", "port")

        logger.info(f"Подключаемся к базе данных по адресу {db_host}:{db_port}...")
        # ... логика подключения ...
        logger.info("Успешно подключились!")

    def main():
        logger.info("Приложение запущено.")
        connect_to_db()
        api_token = get_config_value("API", "token")
        logger.debug(f"Используемый токен API: {api_token[:4]}****")
        logger.info("Приложение завершило работу.")

    if __name__ == "__main__":
        main()
    ```

3.  Запустите ваш скрипт. Вы увидите логи в консоли, а в проекте появится папка `logs` с файлом лога.

## API и Использование

### Работа с конфигурацией (`chutils.config`)

- `get_config_value(section, key, fallback="")`: Получить строковое значение.
- `get_config_int(section, key, fallback=0)`: Получить целое число.
- `get_config_boolean(section, key, fallback=False)`: Получить булево значение.
- `get_config_list(section, key, fallback=[])`: Получить список строк из многострочного значения.
- `save_config_value(section, key, value)`: Сохранить значение в `config.ini`.

### Настройка логирования (`chutils.logger`)

- `setup_logger(name='app_logger', log_level_str='')`: Настраивает и возвращает стандартный объект `logging.Logger`.

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
# Уровни: DEBUG, INFO, WARNING, ERROR, CRITICAL
log_level = DEBUG
# Имя файла для логов
log_file_name = my_app.log
# Сколько дней хранить файлы логов
log_backup_count = 7
```

## Лицензия

Проект распространяется под лицензией MIT.