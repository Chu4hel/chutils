# Умный HTTP-клиент с ротацией и защитой (chutils.web)

Модуль `chutils.web` предоставляет высокоуровневую обертку над библиотекой `httpx` для выполнения синхронных и
асинхронных HTTP-запросов. Он автоматически решает задачи ротации User-Agent, прокси-серверов, кэширования ответов,
ограничения частоты запросов к хостам и автоматических повторных попыток.

Данный модуль поставляется как опциональный экстра-пакет `chutils[web]`.

## Установка

```bash
pip install "chutils[web]"
```

## Основные возможности

1. **Ротация User-Agent**: Автоматически подставляет случайный User-Agent из встроенного списка популярных браузеров для
   каждого запроса.
2. **Управление пулом прокси (ProxyPool)**: Поддерживает статический список, фоновое обновление по URL-адресу и
   системные прокси-серверы с поддержкой стратегий Round-Robin и Random.
3. **Кэширование ответов**: Автоматическое кэширование успешных GET-запросов (200 OK) с поддержкой TTL.
4. **Ограничение частоты (Rate Limiting)**: Ограничение количества запросов к хостам на основе алгоритмов маркерной
   корзины.
5. **Автоматические повторы (Retries)**: Повтор запросов при сетевых ошибках или 5xx статусах с автоматическим
   переключением прокси на следующую попытку.

---

## Использование

### 1. Простой синхронный клиент

```python
from chutils.web import WebClient

# Все параметры по умолчанию. User-Agent ротируется автоматически.
with WebClient() as client:
    response = client.get("https://httpbin.org/headers")
    print(response.json())
```

### 2. Пул прокси и автосмена при сбоях

При возникновении ошибок сети или тайм-аутов клиент переключается на следующий прокси из пула и пробует выполнить запрос
снова:

```python
from chutils.web import WebClient
from chutils.web.proxy_pool import ProxyPool

# Задаем пул прокси
proxy_pool = ProxyPool(
    proxies=["http://proxy1:8080", "http://proxy2:8080"],
    strategy="round_robin"
)

# Настраиваем WebClient на смену прокси при ошибках (2 повторные попытки)
with WebClient(
        proxy_pool=proxy_pool,
        rotate_proxy=True,
        retries=2,
        retry_delay=1.0
) as client:
    # Запрос автоматически ротирует прокси на каждую попытку в случае сбоя
    resp = client.get("https://httpbin.org/get")
```

### 3. Ограничение частоты и Кэширование

```python
from chutils.web import WebClient

with WebClient(
        rate_limit_calls=5,  # Не более 5 запросов
        rate_limit_period=60.0,  # в минуту к одному хосту
        rate_limit_wait=True,  # Ждать свободного слота (не кидать ошибку)
        cache_ttl=300  # Кэшировать GET-запросы на 5 минут
) as client:
    # Первый запрос пойдет в сеть
    resp1 = client.get("https://httpbin.org/ip")

    # Второй вернется мгновенно из кэша
    resp2 = client.get("https://httpbin.org/ip")
```

### 4. Асинхронный клиент (AsyncWebClient)

Класс `AsyncWebClient` полностью наследует асинхронный интерфейс `httpx.AsyncClient` и предоставляет идентичный набор
функций:

```python
import asyncio
from chutils.web import AsyncWebClient


async def main():
    async with AsyncWebClient(cache_ttl=60) as client:
        resp = await client.get("https://httpbin.org/get")
        print(resp.status_code)


asyncio.run(main())
```

---

## Справочник API параметров конструктора

Оба класса `WebClient` и `AsyncWebClient` принимают следующие дополнительные параметры:

| Параметр              | Тип                | По умолчанию     | Описание                                                                                                             |
|-----------------------|--------------------|------------------|----------------------------------------------------------------------------------------------------------------------|
| `user_agent_rotator`  | `UserAgentRotator` | `None`           | Кастомный объект ротатора User-Agent.                                                                                |
| `proxy_pool`          | `ProxyPool`        | `None`           | Пул прокси-серверов для ротации.                                                                                     |
| `rotate_ua`           | `bool`             | `True`           | Включить/выключить автоматическую подмену User-Agent.                                                                |
| `rotate_proxy`        | `bool`             | `True`           | Включить/выключить переключение прокси при сбоях.                                                                    |
| `retries`             | `int`              | `0`              | Количество повторных попыток при сетевых ошибках/5xx.                                                                |
| `retry_delay`         | `float`            | `1.0`            | Начальная задержка между повторами в секундах.                                                                       |
| `retry_backoff`       | `float`            | `2.0`            | Коэффициент экспоненциального нарастания задержки повтора.                                                           |
| `retry_on_5xx`        | `bool`             | `True`           | Запускать ли повторные попытки при статус-кодах >= 500.                                                              |
| `rate_limit_calls`    | `int \| None`      | `None`           | Максимальное число вызовов к хосту за период.                                                                        |
| `rate_limit_period`   | `float`            | `1.0`            | Длительность периода ограничения частоты (сек).                                                                      |
| `rate_limit_strategy` | `str`              | `"token_bucket"` | Алгоритм лимитера (`"token_bucket"` или `"leaky_bucket"`).                                                           |
| `rate_limit_wait`     | `bool`             | `False`          | Если `True` — приостанавливает запрос до освобождения лимита. Если `False` — сразу бросает `RateLimitExceededError`. |
| `cache_ttl`           | `int \| None`      | `None`           | Время жизни кэша успешных GET-запросов (сек).                                                                        |
| `cache_backend`       | `Any`              | `None`           | Бэкенд кэша (по умолчанию используется `InMemoryCacheBackend`).                                                      |
