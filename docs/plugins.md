# Система плагинов (Plugins)

Система плагинов позволяет расширять возможности `chutils` (добавлять внешние источники настроек, провайдеры секретов, лог-хэндлеры и экспортеры метрик) без раздувания ядра библиотеки. Благодаря этому разработчики могут создавать специализированные пакеты (например, `chutils-aws`, `chutils-sentry`) и подключать их к своим приложениям по мере необходимости.

---

## Точки расширения (Extension Points)

Библиотека предоставляет 6 абстрактных интерфейсов для плагинов:

1. **`SecretProviderPlugin`** — Внешние хранилища секретов (AWS Secrets Manager, HashiCorp Vault, Yandex Lockbox).
2. **`ConfigProviderPlugin`** — Чтение/запись конфигурационных файлов нестандартных форматов (TOML, XML) или внешних распределенных хранилищ (Consul, Etcd).
3. **`LoggerHandlerPlugin`** — Подключение кастомных обработчиков логов Python (`logging.Handler`), например, для отправки логов в Sentry, Datadog или Telegram.
4. **`MetricsPlugin`** — Экспорт метрик в сторонние системы сбора телеметрии (Datadog, StatsD, OpenTelemetry).
5. **`CaptchaSolverPlugin`** — Внешние и кастомные сервисы решения капчи (2Captcha, Capsolver, локальные ML-модели).
6. **`TaskQueuePlugin`** — Распределенные бэкенды очередей задач скрапинга (RabbitMQ, NATS, Kafka).

---

## Жизненный цикл и ленивая загрузка (Lazy Loading)

Для сохранения высокой скорости холодного старта приложения система плагинов использует принцип **ленивой загрузки**:

* Плагины **не импортируются** и **не инициализируются** при импорте `chutils`.
* Автообнаружение и загрузка плагинов происходят только в тот момент, когда приложение впервые обращается к соответствующей подсистеме (например, при вызове `SecretManager.get_secret()`, `setup_logger()` или `get_config()`).
* Если плагин содержит синтаксическую ошибку или требует отсутствующие зависимости, возникшее исключение изолируется. Сбойный плагин игнорируется (логируется предупреждение), а приложение продолжает работу.

---

## Способы подключения плагинов

Поддерживаются два механизма регистрации: автообнаружение (через entry points) и ручная регистрация в коде.

### 1. Автообнаружение через Entry Points (Рекомендуется)

Если вы публикуете плагин в виде отдельного Python-пакета, зарегистрируйте его в `pyproject.toml` (или `setup.py`) вашего проекта в соответствующей группе `entry_points`.

Пример конфигурации `pyproject.toml` для плагина:

```toml
[tool.poetry.plugins."chutils.plugins.secret"]
aws_secrets = "chutils_aws.secrets:AWSSecretPlugin"

[tool.poetry.plugins."chutils.plugins.config"]
toml_config = "chutils_toml.config:TOMLConfigPlugin"

[tool.poetry.plugins."chutils.plugins.logger"]
sentry_logger = "chutils_sentry.logger:SentryLoggerPlugin"

[tool.poetry.plugins."chutils.plugins.metrics"]
datadog_metrics = "chutils_datadog.metrics:DatadogMetricsPlugin"
```

При первом обращении к подсистеме `chutils` автоматически найдет установленный пакет по указанному пути и зарегистрирует его экземпляр.

### 2. Ручная (явная) регистрация

Для локальной разработки или тестирования плагины можно зарегистрировать напрямую в коде приложения с помощью функции `register_plugin()`:

```python
from chutils.plugins import register_plugin, SecretProviderPlugin

class LocalSecretPlugin(SecretProviderPlugin):
    @property
    def name(self) -> str:
        return "local_vault"

    def get(self, key: str, service_name: str) -> str | None:
        if key == "API_KEY":
            return "my-local-secret"
        return None

    def set(self, key: str, value: str, service_name: str) -> bool:
        return True

    def delete(self, key: str, service_name: str) -> bool:
        return True

# Явно регистрируем плагин до инициализации подсистем
register_plugin(LocalSecretPlugin())
```

---

## Создание собственного плагина

Все плагины должны наследоваться от `BasePlugin` (предоставляющего уникальный атрибут `name`) и соответствующего интерфейса точки расширения.

### 1. Плагин-провайдер секретов (`SecretProviderPlugin`)

```python
from typing import Optional
from chutils.plugins import SecretProviderPlugin

class VaultSecretPlugin(SecretProviderPlugin):
    @property
    def name(self) -> str:
        return "hashicorp_vault"

    def get(self, key: str, service_name: str) -> Optional[str]:
        # Логика получения секрета из Vault
        return "decrypted_value"

    def set(self, key: str, value: str, service_name: str) -> bool:
        # Логика сохранения секрета в Vault
        return True

    def delete(self, key: str, service_name: str) -> bool:
        # Логика удаления
        return True
```

### 2. Плагин-провайдер конфигураций (`ConfigProviderPlugin`)

Если плагин поддерживает определенные расширения файлов, он должен декларировать свойство `supported_extensions`. Если свойство отсутствует, плагин будет зарегистрирован для расширения, совпадающего с его `name` (с добавлением ведущей точки).

```python
from typing import Any
from chutils.plugins import ConfigProviderPlugin
from chutils.typing import JSONDict

class TOMLConfigPlugin(ConfigProviderPlugin):
    @property
    def name(self) -> str:
        return "toml_provider"

    @property
    def supported_extensions(self) -> list[str]:
        return [".toml"]

    def load(self, path: str) -> JSONDict:
        # Логика парсинга TOML
        import toml
        with open(path, "r", encoding="utf-8") as f:
            return toml.load(f)

    def save(self, path: str, section: str, key: str, value: Any) -> bool:
        # Логика сохранения в TOML
        return True
```

### 3. Плагин лог-хэндлера (`LoggerHandlerPlugin`)

Позволяет инжектировать кастомные хэндлеры в процесс конфигурации логов.

```python
import logging
from typing import Any
from chutils.plugins import LoggerHandlerPlugin

class SentryHandlerPlugin(LoggerHandlerPlugin):
    @property
    def name(self) -> str:
        return "sentry_handler"

    def get_handler(self, **kwargs: Any) -> logging.Handler:
        # Инициализируем и возвращаем хэндлер
        # kwargs содержит объединенные параметры настроек логгера
        from sentry_sdk.integrations.logging import EventHandler
        return EventHandler()
```

### 4. Плагин метрик (`MetricsPlugin`)

Позволяет экспортировать показатели в сторонние агрегаторы.

```python
from typing import Dict, Optional
from chutils.plugins import MetricsPlugin

class DatadogMetricsPlugin(MetricsPlugin):
    @property
    def name(self) -> str:
        return "datadog"

    def increment(self, name: str, value: float = 1.0, labels: Optional[Dict[str, str]] = None) -> None:
        # Отправка в Datadog
        pass

    def set_gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        pass

    def observe(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        pass

    def generate_latest(self) -> str:
        return ""

    def clear(self) -> None:
        pass
```
