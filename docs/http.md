# HTTP-клиент и долгоживущие соединения (chutils.http)

Модуль `chutils.http` предоставляет гибкий и мощный HTTP-клиент на базе `httpx`, а также инструменты для работы с
долгоживущими соединениями в подмодуле `chutils.http.streaming`:

1. **HTTP Streaming и SSE (Server-Sent Events)** (на стандартных зависимостях `httpx`).
2. **WebSockets** (требует опциональной установки `chutils[websockets]`).

---

## Установка

Для использования базового HTTP-клиента и SSE-стриминга:

```bash
pip install "chutils[web]"
```

Для поддержки WebSockets:

```bash
pip install "chutils[websockets]"
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

    client = EventStreamClient(url, filter_heartbeats=True)
    with client:
        for event in client:
            print(f"Data: {event.data}")


if __name__ == "__main__":
    main()
```

---

## WebSockets

Для работы с WebSockets используются клиенты `AsyncWebSocketClient` (асинхронный) и `WebSocketClient` (синхронный). При
отсутствии установленной библиотеки `websockets` выбрасывается `OptionalDependencyError`.

### 1. Асинхронный WebSocket-клиент (AsyncWebSocketClient)

```python
import asyncio
from chutils.http.streaming import AsyncWebSocketClient


async def main():
    url = "ws://echo.websocket.org"

    # Авто-реконнект с бэкоффом по умолчанию включен.
    # filter_heartbeats=True отфильтровывает пустые кадры-пинги.
    client = AsyncWebSocketClient(url, filter_heartbeats=True)

    async with client as ws:
        await ws.send("Привет, WebSocket!")

        # Получение сообщений через recv()
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
client = AsyncWebSocketClient(
    "ws://example.com/ws",
    reconnect_strategy=[0.1, 0.5, 1.0]
)
```
