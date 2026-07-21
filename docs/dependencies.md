# Опциональные зависимости

Библиотека `chutils` спроектирована по принципу **минимального ядра**: базовая установка (`pip install chutils`)
включает только самые необходимые пакеты. Расширенная функциональность активируется через
**опциональные группы зависимостей** (extras).

---

## Быстрая установка

```bash
# Минимальная установка (ядро)
pip install chutils

# Одна дополнительная группа
pip install "chutils[rich]"

# Несколько групп сразу
pip install "chutils[rich,secrets,crypto]"

# Всё включено
pip install "chutils[full]"
```

---

## Карта зависимостей по модулям

В таблице ниже указано, какая группа (extra) требуется для каждого модуля или функции.
Если группа не установлена, будет выброшено исключение `OptionalDependencyError` или
функциональность будет автоматически деградирована (отмечено иконкой ⚡).

| Extra      | Пакет                                                                                  | Модули и функции                                                                                                                                                                                                                                                                                                                                             | Поведение при отсутствии                                                                                                              |
|------------|----------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------|
| `secrets`  | `keyring >=25.7`                                                                       | `chutils.secret_manager` — провайдер `KeyringProvider`                                                                                                                                                                                                                                                                                                       | ⚡ `SecretManager` автоматически отключает `KeyringProvider` и работает только через Env / DotEnv. Однократное предупреждение в логах. |
| `aws`      | `boto3 >=1.34`                                                                         | `chutils.secret_manager` — провайдер `AWSSecretManagerProvider`                                                                                                                                                                                                                                                                                              | `OptionalDependencyError` при попытке использовать `AWSSecretManagerProvider` без `boto3`                                             |
| `gcp`      | `google-cloud-secret-manager >=2.20`                                                   | `chutils.secret_manager` — провайдер `GCPSecretManagerProvider`                                                                                                                                                                                                                                                                                              | `OptionalDependencyError` при попытке использовать `GCPSecretManagerProvider` без SDK                                                 |
| `pydantic` | `pydantic >=2.13`                                                                      | `chutils.config.get_config()` (параметр `model`), `chutils.config.get_config_value()` (параметр `model`), `chutils.config.export_schema()`, `chutils.config.import_model_class()`, `chutils.config.generate_yaml_template()`, `chutils.config.generate_env_template()`, `chutils.config.generate_json_schema()`, CLI: `chutils validate`, `chutils template` | `OptionalDependencyError` при вызове                                                                                                  |
| `watch`    | `watchdog >=6.0`                                                                       | `chutils.config.start_config_watcher()`                                                                                                                                                                                                                                                                                                                      | `OptionalDependencyError` при вызове                                                                                                  |
| `rich`     | `rich >=15.0`                                                                          | `chutils.logger` — Rich-форматирование логов, `chutils.cli` — красивый вывод CLI, `chutils.cli_utils.get_console()`                                                                                                                                                                                                                                          | ⚡ Автоматический fallback на стандартный `logging.StreamHandler` и простой текстовый вывод                                            |
| `json`     | `python-json-logger >=3.2`                                                             | `chutils.logger` — JSON-формат логов (`ChutilsJsonFormatter`)                                                                                                                                                                                                                                                                                                | ⚡ JSON-форматирование недоступно; используется стандартный текстовый формат                                                           |
| `date`     | `python-dateutil >=2.9`                                                                | `chutils.time.parse_datetime()`                                                                                                                                                                                                                                                                                                                              | ⚡ Парсинг дат ограничен стандартным `datetime.fromisoformat()`                                                                        |
| `metrics`  | `prometheus-client >=0.20`                                                             | `chutils.metrics.prometheus` — класс `PrometheusMetrics`                                                                                                                                                                                                                                                                                                     | `OptionalDependencyError` при инициализации                                                                                           |
| `text`     | `rapidfuzz >=3.9`                                                                      | `chutils.text.is_significant_difference()`                                                                                                                                                                                                                                                                                                                   | `OptionalDependencyError` при вызове                                                                                                  |
| `crypto`     | `cryptography >=42.0`                                                                  | `chutils.crypto` — `encrypt_portable()`, `decrypt_portable()`, `encrypt_file()`, `decrypt_file()`                                                                                                                                                                                                                                                            | `OptionalDependencyError` при вызове                                                                                                  |
| `web`        | `httpx >=0.27`                                                                         | `chutils.web` — `WebClient`, `AsyncWebClient`, `ProxyPool`, `UserAgentRotator`; умный HTTP-клиент с ротацией прокси и User-Agent                                                                                                                                                                                                                             | `OptionalDependencyError` при вызове                                                                                                  |
| `websockets` | `websockets >=14.0`                                                                    | `chutils.http.streaming` — `AsyncWebSocketClient`, `WebSocketClient`; клиенты для работы с WebSockets                                                                                                                                                                                                                                                        | `OptionalDependencyError` при вызове                                                                                                  |
| `captcha`    | `httpx >=0.27`                                                                         | `chutils.scraping.captcha` — клиенты RuCaptcha/2Captcha, Anti-Captcha, CapMonster Cloud (`RuCaptchaSolver`, `AntiCaptchaSolver`, `CapMonsterSolver`)                                                                                                                                                                                                         | `OptionalDependencyError` при вызове                                                                                                  |
| `scraping`   | `playwright >=1.49`, `selenium >=4.27`                                                 | `chutils.scraping.humanize` — имитация поведения человека (мышь, клавиатура, паузы), анти-детекция (`apply_antidetect_playwright`, `apply_antidetect_selenium`)                                                                                                                                                                                              | `OptionalDependencyError` при вызове                                                                                                  |
| `otel`       | `opentelemetry-api`, `opentelemetry-sdk`, `opentelemetry-exporter-otlp` (все `>=1.41`) | `chutils.tracing` — `setup_tracing()`, `@traced`, `get_tracer()`                                                                                                                                                                                                                                                                                             | ⚡ Декоратор `@traced` становится no-op (просто возвращает оригинальную функцию). `get_tracer()` возвращает `None`.                    |
| `testing`    | `pytest >=9.0`                                                                         | `chutils.testing` — фикстуры для тестов (`temp_config`, `mock_secret_manager` и др.)                                                                                                                                                                                                                                                                         | `ImportError` при попытке импорта                                                                                                     |
| `full`       | Все вышеперечисленные                                                                  | Вся функциональность                                                                                                                                                                                                                                                                                                                                         | —                                                                                                                                     |

---

## Типы поведения при отсутствии зависимости

### ⚡ Изящная деградация (Graceful Degradation)

Модули, отмеченные значком ⚡, **не выбрасывают ошибку** при отсутствии зависимости.
Вместо этого они автоматически переключаются на более простой, встроенный вариант работы:

```python
# rich не установлен — вывод будет простым текстом, без ошибок
from chutils.cli_utils import get_console

console = get_console()  # вернёт fallback-обёртку
```

### `OptionalDependencyError`

Модули без пометки ⚡ выбрасывают специализированное исключение при попытке использования
недоступной функциональности:

```python
from chutils.exceptions import OptionalDependencyError

try:
    from chutils.crypto import encrypt_portable

    result = encrypt_portable("секретные данные", "seed")
except OptionalDependencyError as e:
    print(f"Ошибка: {e.message}")
    print(f"Совет: {e.hint}")
    # Ошибка: Required package 'cryptography' is not installed.
    # Совет: pip install chutils[crypto]
```

---

## Рекомендации по выбору

| Сценарий                                   | Рекомендуемая установка           |
|--------------------------------------------|-----------------------------------|
| Микросервис с YAML-конфигом                | `pip install chutils`             |
| Проект с красивым CLI-выводом              | `pip install "chutils[rich]"`     |
| Проект с секретами в системном хранилище   | `pip install "chutils[secrets]"`  |
| Проект с Pydantic-моделями конфигурации    | `pip install "chutils[pydantic]"` |
| Автоматический hot-reload конфигурации     | `pip install "chutils[watch]"`    |
| Шифрование конфиденциальных данных         | `pip install "chutils[crypto]"`   |
| Мониторинг метрик через Prometheus         | `pip install "chutils[metrics]"`  |
| Нечёткое сравнение текстов                 | `pip install "chutils[text]"`     |
| Распределённая трассировка (OpenTelemetry) | `pip install "chutils[otel]"`     |
| Умный HTTP-клиент с ротацией proxy/UA      | `pip install "chutils[web]"`      |
| Интеграция с решателями капчи              | `pip install "chutils[captcha]"`  |
| Автоматизация браузера / анти-детекция     | `pip install "chutils[scraping]"` |
| Полная установка для разработки            | `pip install "chutils[full]"`     |

---

*Последнее обновление карты зависимостей: 2026-07-16 (для версии 3.1.0).*
