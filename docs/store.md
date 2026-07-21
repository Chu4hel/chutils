# chutils.store — Абстракция Key-Value хранилища

Модуль `chutils.store` предоставляет универсальный единый интерфейс для работы с Key-Value хранилищами (Memory, Redis,
Memcached) с прозрачной сериализацией, поддержкой TTL, авто-префиксов, метрик, трассировки и декоратором кэширования
`@store_cache`.

---

## 1. Основные концепции

- **`BaseStoreBackend`**: Абстрактный базовый класс бэкендов.
- **`MemoryStore`**: Потокобезопасное in-memory хранилище (работает без внешних зависимостей).
- **`RedisStore`**: Бэкенд для Redis (требует опциональный пакет `redis`).
- **`MemcachedStore`**: Бэкенд для Memcached (требует `pymemcache` / `aiomemcache`).
- **`StoreManager`**: Единый менеджер для выполнения синхронных и асинхронных операций с поддержкой сериализации (
  `json`, `pickle`, `raw`).
- **`@store_cache`**: Декоратор для прозрачного кэширования вызовов синхронных и асинхронных функций.

---

## 2. Использование StoreManager

### Синхронное использование:

```python
from chutils.store import StoreManager, MemoryStore

# Создание менеджера с in-memory бэкендом
store = StoreManager(backend=MemoryStore(), serializer="json", prefix="app:")

# Сохранение и чтение
store.set("user:1", {"name": "Alice", "role": "admin"}, ttl=3600)
user = store.get("user:1")
print(user["name"])  # "Alice"

# Проверка существования и удаление
if store.exists("user:1"):
    store.delete("user:1")
```

### Асинхронное использование:

```python
import asyncio
from chutils.store import StoreManager, RedisStore


async def main():
    # Инициализация Redis бэкенда
    store = StoreManager(backend=RedisStore(url="redis://localhost:6379/0"), serializer="json")

    await store.aset("session:token123", {"user_id": 42}, ttl=300)
    data = await store.aget("session:token123")
    print(data)

    await store.adelete("session:token123")


asyncio.run(main())
```

---

## 3. Декоратор кэширования `@store_cache`

```python
from chutils.store import store_cache, StoreManager

store = StoreManager()


@store_cache(store=store, ttl=120)
def fetch_heavy_data(item_id: int) -> dict:
    # Тяжелое вычисление или запрос к БД
    return {"id": item_id, "status": "active"}


# Первый вызов — выполнение функции
res1 = fetch_heavy_data(10)

# Второй вызов — быстрая отдача из кэша
res2 = fetch_heavy_data(10)

# Ручная инвалидация конкретного вызова
fetch_heavy_data.invalidate(10)
```

---

## 4. Конфигурация в `pyproject.toml`

```toml
[tool.chutils.store]
backend = "redis"
url = "redis://localhost:6379/0"
serializer = "json"
prefix = "prod:"
```
