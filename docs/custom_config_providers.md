# Custom Config Providers API

> **Доступно с версии 3.2.0** · Модуль: `chutils.config`

Custom Config Providers — это расширяемый API для интеграции **внешних источников
конфигурации** (БД, Redis, Consul, Vault, удалённые API и др.) в единый интерфейс
`chutils.config`. Он позволяет динамически переопределять настройки в рантайме без
изменения локальных файлов `config.yml`.

---

## Быстрый старт

```python
from chutils.config import register_provider, get_config_value
from chutils.config.custom_providers import DictConfigProvider

# 1. Создаём провайдер
provider = DictConfigProvider({
    "database": {"host": "prod-db.internal", "port": "5432"},
    "app": {"debug": "false"},
})

# 2. Регистрируем (priority=10 — высокий приоритет)
register_provider(provider, priority=10)

# 3. Используем стандартный API — провайдер опрашивается автоматически
host = get_config_value("database", "host")
# → "prod-db.internal"
```

---

## Порядок приоритетов

При вызове `get_config_value` / `aget_config_value` источники опрашиваются
в следующем порядке (от высшего к низшему):

| # | Источник                 | Описание                                             |
|---|--------------------------|------------------------------------------------------|
| 1 | **Кастомные провайдеры** | По числовому приоритету (`priority`). Меньше → выше. |
| 2 | Переменные окружения     | `CH_[SECTION]_[KEY]`                                 |
| 3 | `config.local.yml`       | Локальные переопределения (не коммитятся)            |
| 4 | `config.{CH_ENV}.yml`    | Файл окружения (production, staging…)                |
| 5 | `config.yml`             | Базовые настройки                                    |

> **Важно:** если провайдер вернул `None` — поиск продолжается к следующему
> источнику. Возврат `None` означает «не знаю», а не «значение отсутствует».

---

## Реализация собственного провайдера

Унаследуйтесь от `BaseConfigProvider` и реализуйте два метода:

```python
from typing import Any
from chutils.config.custom_providers import BaseConfigProvider


class RedisConfigProvider(BaseConfigProvider):
    """Провайдер, читающий настройки из Redis Hash."""

    def __init__(self, redis_client, hash_key: str = "app:config") -> None:
        self._redis = redis_client
        self._hash_key = hash_key

    def get_value(self, section: str, key: str) -> Any | None:
        # Ключ в Redis: "section:key"
        field = f"{section.lower()}:{key.lower()}"
        value = self._redis.hget(self._hash_key, field)
        return value.decode() if value else None

    async def aget_value(self, section: str, key: str) -> Any | None:
        field = f"{section.lower()}:{key.lower()}"
        value = await self._redis.hget(self._hash_key, field)
        return value.decode() if value else None
```

Регистрация:

```python
import redis.asyncio as redis
from chutils.config import register_provider

client = redis.Redis(host="localhost")
register_provider(RedisConfigProvider(client), priority=5)
```

---

## Пример: SQLAlchemyConfigProvider

Пример полноценного провайдера для хранения конфигурации в реляционной БД
через SQLAlchemy. Значения берутся из таблицы `config_entries`.

### Схема таблицы

```sql
CREATE TABLE config_entries
(
    id      SERIAL PRIMARY KEY,
    section VARCHAR(128) NOT NULL,
    key     VARCHAR(128) NOT NULL,
    value   TEXT,
    UNIQUE (section, key)
);
```

### Реализация

```python
from __future__ import annotations

import asyncio
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from chutils.config.custom_providers import BaseConfigProvider


class SQLAlchemyConfigProvider(BaseConfigProvider):
    """Провайдер конфигурации на базе SQLAlchemy (async).

    Читает значения из таблицы ``config_entries``.
    Поддерживает TTL-кэш для снижения нагрузки на БД.

    Args:
        dsn: DSN для подключения к БД (asyncpg / aiosqlite и др.).
        cache_ttl: Время жизни кэша в секундах. 0 = без кэша.
    """

    def __init__(self, dsn: str, cache_ttl: int = 60) -> None:
        self._engine: AsyncEngine = create_async_engine(dsn, pool_pre_ping=True)
        self._session_factory = sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False
        )
        self._cache: dict[str, Any] = {}
        self._cache_ttl = cache_ttl
        self._cache_ts: dict[str, float] = {}

    # ------------------------------------------------------------------
    # Публичный интерфейс BaseConfigProvider
    # ------------------------------------------------------------------

    def get_value(self, section: str, key: str) -> Any | None:
        """Синхронная обёртка — запускает async-метод в executor."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # Нет активного event loop — создаём временный
            return asyncio.run(self.aget_value(section, key))
        else:
            # Есть event loop — нельзя вызвать asyncio.run(), используем
            # синхронное чтение из кэша или возвращаем None
            cache_key = f"{section.lower()}:{key.lower()}"
            return self._cache.get(cache_key)

    async def aget_value(self, section: str, key: str) -> Any | None:
        """Асинхронно читает значение из БД с кэшированием."""
        import time

        cache_key = f"{section.lower()}:{key.lower()}"

        # Проверяем кэш
        if self._cache_ttl > 0 and cache_key in self._cache:
            age = time.monotonic() - self._cache_ts.get(cache_key, 0)
            if age < self._cache_ttl:
                return self._cache[cache_key]

        # Запрос к БД
        async with self._session_factory() as session:
            row = await session.execute(
                text(
                    "SELECT value FROM config_entries "
                    "WHERE LOWER(section) = :section AND LOWER(key) = :key "
                    "LIMIT 1"
                ),
                {"section": section.lower(), "key": key.lower()},
            )
            result = row.scalar_one_or_none()

        if result is not None:
            self._cache[cache_key] = result
            self._cache_ts[cache_key] = time.monotonic()

        return result

    async def close(self) -> None:
        """Закрывает соединение с БД."""
        await self._engine.dispose()
```

### Использование

```python
from chutils.config import register_provider, get_config_value, aget_config_value

# При старте приложения
provider = SQLAlchemyConfigProvider(
    dsn="postgresql+asyncpg://user:pass@db/myapp",
    cache_ttl=30,
)
register_provider(provider, priority=10)

# Синхронный доступ (читает из кэша провайдера)
db_host = get_config_value("database", "host", fallback="localhost")


# Асинхронный доступ (опрашивает БД напрямую)
async def get_db_host() -> str:
    return await aget_config_value("database", "host", fallback="localhost")
```

---

## `DictConfigProvider` — для тестов

Встроенный провайдер на основе словаря. Идеален для мокирования настроек
в unit-тестах:

```python
import pytest
from chutils.config import register_provider, reset_providers, get_config_value
from chutils.config.custom_providers import DictConfigProvider


@pytest.fixture(autouse=True)
def mock_config():
    provider = DictConfigProvider({
        "database": {"host": "test-db", "port": "5432"},
        "app": {"debug": "true", "log_level": "DEBUG"},
    })
    register_provider(provider, priority=0)  # priority=0 → максимальный приоритет
    yield
    reset_providers()  # обязательно сбрасываем после теста


def test_something():
    assert get_config_value("database", "host") == "test-db"
```

---

## Справочник API

### `register_provider(provider, priority=100)`

Регистрирует провайдер в глобальном реестре.

| Параметр   | Тип                  | Описание                                     |
|------------|----------------------|----------------------------------------------|
| `provider` | `BaseConfigProvider` | Экземпляр провайдера                         |
| `priority` | `int`                | Приоритет (меньше → выше, по умолчанию: 100) |

### `reset_providers()`

Очищает реестр. Вызывайте в `teardown` тестов.

### `get_config_value(section, key, fallback=None, ...)`

Синхронное чтение значения. Автоматически опрашивает зарегистрированные провайдеры.

### `aget_config_value(section, key, fallback=None, ...)`

Асинхронное чтение. Вызывает `aget_value()` провайдеров без блокировки event loop.

### `BaseConfigProvider`

Абстрактный класс. Обязательные методы:

```python
def get_value(self, section: str, key: str) -> Any | None: ...


async def aget_value(self, section: str, key: str) -> Any | None: ...
```

### `DictConfigProvider(data)`

Готовый провайдер на словаре. Ключи секций и полей нечувствительны к регистру.

---

## Советы и ограничения

- **Возврат `None`** — сигнал «ключ не найден», поиск продолжается дальше.
- **Ошибки в провайдере** логируются и не прерывают работу — следующий
  провайдер опрашивается в штатном режиме.
- **Порядок при одинаковом `priority`** — FIFO (первый зарегистрированный побеждает).
- **Потокобезопасность** — реестр защищён `threading.RLock`.
- **Кэш конфигурации** `chutils` не очищается автоматически при регистрации нового
  провайдера. Если провайдер должен перекрыть уже загруженный кэш — используйте
  `chutils.config.clear_cache()` перед регистрацией.
