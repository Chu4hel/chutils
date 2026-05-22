# Тестирование с chutils

Библиотека `chutils` предоставляет набор готовых `pytest` фикстур, которые значительно упрощают тестирование приложений,
использующих конфигурацию, секреты или логирование `chutils`.

Эти инструменты позволяют изолировать тесты от реальной файловой системы, системного хранилища секретов (Keyring) и
проверять вывод логов.

## Подключение фикстур

Фикстуры находятся в модуле `chutils.testing.fixtures`. Чтобы они стали доступны во всех ваших тестах, добавьте
следующую строку в ваш `tests/conftest.py`:

```python
pytest_plugins = ["chutils.testing.fixtures"]
```

Или импортируйте их явно в нужном тестовом файле:

```python
from chutils.testing.fixtures import mock_chutils_config, mock_chutils_secrets, capture_chutils_logs
```

---

## 1. Мокирование конфигурации (`mock_chutils_config`)

Фикстура `mock_chutils_config` позволяет устанавливать любые значения конфигурации, которые будут возвращаться функциями
`get_config_value`, `get_config_int` и другими.

**Особенности:**

- Автоматически отключает переопределение через переменные окружения (`CH_DISABLE_ENV_OVERRIDE=true`) для
  предсказуемости тестов.
- Сбрасывает состояние конфигурации после каждого теста.

### Пример использования

```python
def test_database_connection(mock_chutils_config):
    # Устанавливаем тестовые значения
    mock_chutils_config.set("database", "host", "localhost")
    mock_chutils_config.set("database", "port", 5432)

    from chutils import get_config_value
    assert get_config_value("database", "host") == "localhost"
```

---

## 2. Мокирование секретов (`mock_chutils_secrets`)

Фикстура `mock_chutils_secrets` подменяет реальные провайдеры секретов (например, Keyring) на простое хранилище в
памяти. Это предотвращает чтение реальных секретов с вашей машины во время тестов.

### Пример использования

```python
def test_api_client(mock_chutils_secrets):
    # Предустанавливаем "фейковый" секрет
    mock_chutils_secrets.set_secret("api_token", "test-token-123")

    from chutils import SecretManager
    sm = SecretManager(service_name="my_service")

    assert sm.get_secret("api_token") == "test-token-123"
```

---

## 3. Перехват логов (`capture_chutils_logs`)

Фикстура `capture_chutils_logs` позволяет проверять, какие сообщения были отправлены в логгер, а также инспектировать
поля контекста (например, добавленные через `bind_context`).

### Пример использования

```python
from chutils import setup_logger, bind_context


def test_logging_behavior(capture_chutils_logs):
    logger = setup_logger("my_app")

    with bind_context(request_id="abc"):
        logger.info("Processing started")

    # Проверка наличия сообщения
    assert capture_chutils_logs.has_message("Processing started")

    # Проверка по подстроке
    assert capture_chutils_logs.has_message("started", partial=True)

    # Проверка по полям контекста
    records = capture_chutils_logs.get_by_field("request_id", "abc")
    assert len(records) == 1
    assert records[0].getMessage() == "Processing started"
```

## Полный пример

Готовый пример использования всех фикстур вместе можно найти в файле `examples/25_testing_fixtures_example.py`.
