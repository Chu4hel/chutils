# HTTP-клиент, долгоживущие соединения и TLS Impersonation (chutils.http)

Модуль `chutils.http` предоставляет гибкий и мощный HTTP-клиент на базе `httpx`, TLS-клиент для обхода защиты Cloudflare/WAF на базе `curl-cffi`, а также инструменты для работы с долгоживущими соединениями в подмодуле `chutils.http.streaming`:

1. **TLS Client Impersonation (`TLSSession`, `TLSAsyncClient`)**: Эмуляция отпечатков браузеров JA3/JA4/HTTP2 (Chrome, Safari) для обхода Cloudflare/WAF (опциональная установка `chutils[tls]`).
2. **HTTP Streaming и SSE (Server-Sent Events)** (на стандартных зависимостях `httpx`).
3. **WebSockets** (требует опциональной установки `chutils[websockets]`).

---

## Установка

Для использования базового HTTP-клиента и SSE-стриминга:

```bash
pip install "chutils[web]"
```

Для поддержки TLS Client Impersonation (`curl-cffi`):

```bash
pip install "chutils[tls]"
```

Для поддержки WebSockets:

```bash
pip install "chutils[websockets]"
```

---

## TLS Client Impersonation (curl-cffi)

Подмодуль `chutils.http.tls_client` позволяет выполнять HTTP-запросы с полной подменой параметров TLS/JA3/JA4/HTTP2 под реальные браузеры, что позволяет обходить защиту WAF (Cloudflare, Akamai, DataDome) без запуска тяжелых headless-браузеров.

При отсутствии установленной библиотеки `curl-cffi` клиенты автоматически выполняют graceful fallback на `httpx` (с сохранением базовой работоспособности) либо выбрасывают информативный `OptionalDependencyError` при прямом вызове фабрик.

### 1. Асинхронный TLS-клиент (`TLSAsyncClient`)

```python
import asyncio
from chutils.http import TLSAsyncClient


async def main():
    # impersonate может быть 'chrome120', 'safari17_0' и др.
    client = TLSAsyncClient(impersonate="chrome120", timeout=15.0)

    # Выполнение GET-запроса
    resp = await client.get("https://tls.peet.ws/api/all")
    print(f"Статус: {resp.status_code}")
    print(f"JA3/JA4 Fingerprint: {resp.text}")

    # Закрытие клиента
    await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
```

### 2. Синхронная сессия (`TLSSession`)

```python
from chutils.http import TLSSession

with TLSSession(impersonate="chrome120") as session:
    resp = session.get("https://httpbin.org/get")
    print(resp.json())
```

### 3. Интеграция с ProxyPool и туннелированием

Клиенты `TLSAsyncClient` и `TLSSession` прозрачно интегрированы с подсистемой `chutils.scraping.proxy`:

```python
from chutils.http import TLSAsyncClient
from chutils.scraping.proxy import ProxyPool

pool = ProxyPool.from_urls(["http://user:pass@1.2.3.4:8080"])
client = TLSAsyncClient(proxy_pool=pool, impersonate="chrome120")
```

### 4. Мост браузерных сессий (`from_browser_session`)

Позволяет переносить куки (включая `cf_clearance`) и `User-Agent` из браузера (Playwright, Nodriver, Selenium) напрямую в легковесный TLS-клиент. После прохождения интерактивного челленджа в браузере вся остальная работа может продолжаться на максимальной скорости без накладных расходов браузера:

```python
from chutils.http import TLSAsyncClient, TLSSession

# Асинхронно из Playwright Page или Nodriver Tab:
client = await TLSAsyncClient.from_browser_session(
    page, impersonate="chrome120"
)
resp = await client.get("https://api.example.com/protected/data")

# Синхронно из Selenium WebDriver:
session = TLSSession.from_browser_session(
    driver, impersonate="chrome120"
)
resp = session.get("https://api.example.com/protected/data")
```

---

## Server-Sent Events (SSE)

Для работы с SSE используются клиенты `AsyncEventStreamClient` (асинхронный) и `EventStreamClient` (синхронный).

### 1. Асинхронный SSE-стриминг (AsyncEventStreamClient)

```python
import asyncio
from chutils.http.streaming import AsyncEventStreamClient


async def main():
    url = "https://api.example.com/events"
    headers = {"Authorization": "Bearer your-token"}

    # filter_heartbeats=True автоматически отфильтровывает пустые строки и комментарии (: keepalive)
    client = AsyncEventStreamClient(url, headers=headers, filter_heartbeats=True)

    async with client:
        async for event in client:
            print(f"ID: {event.id}, Event: {event.event}, Data: {event.data}")


if __name__ == "__main__":
    asyncio.run(main())
```

### 2. Синхронный SSE-стриминг (EventStreamClient)

```python
from chutils.http.streaming import EventStreamClient


def main():
    url = "https://api.example.com/events"
    client = EventStreamClient(url)

    with client:
        for event in client:
            print(f"Event: {event.event}, Data: {event.data}")


if __name__ == "__main__":
    main()
```

---

## WebSockets

Для работы с WebSocket-соединениями используются клиенты `AsyncWebSocketClient` (асинхронный) и `WebSocketClient` (синхронный).

### 1. Асинхронный WebSocket-клиент (AsyncWebSocketClient)

```python
import asyncio
from chutils.http.streaming import AsyncWebSocketClient


async def main():
    url = "ws://echo.websocket.org"

    client = AsyncWebSocketClient(url)
    async with client as ws:
        await ws.send("Привет, WebSocket!")
        response = await ws.recv()
        print(f"Ответ: {response}")

        # Или асинхронное итерирование по входящим сообщениям
        async for message in ws:
            print(f"Получено сообщение: {message}")


if __name__ == "__main__":
    asyncio.run(main())
```

### 2. Синхронный WebSocket-клиент (WebSocketClient)

```python
from chutils.http.streaming import WebSocketClient


def main():
    url = "ws://echo.websocket.org"

    client = WebSocketClient(url)
    with client as ws:
        ws.send("Привет, синхронный WebSocket!")
        response = ws.recv()
        print(f"Ответ: {response}")

        # Также поддерживается синхронное итерирование
        for message in ws:
            print(f"Сообщение: {message}")


if __name__ == "__main__":
    main()
```

---

## Автоматическое переподключение (Auto-Reconnect)

По умолчанию клиенты SSE и WebSocket автоматически переподключаются при обрыве соединения, используя алгоритм
экспоненциальной задержки с добавлением случайного шума (Full Jitter).

Вы можете настроить кастомную стратегию ожидания перед переподключением, передав параметр `reconnect_strategy`.

### Пример кастомной стратегии:

```python
from chutils.http.streaming import AsyncWebSocketClient

# Передаем список фиксированных задержек в секундах.
# После 3 попыток (0.1с, 0.5с, 1.0с) клиент пробросит ошибку соединения дальше.
client = AsyncWebSocketClient("ws://example.com/ws", reconnect_strategy=[0.1, 0.5, 1.0])
```
