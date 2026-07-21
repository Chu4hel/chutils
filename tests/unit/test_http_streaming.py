"""
Тесты для chutils.http.streaming.
Проверяет:
- AsyncEventStreamClient / EventStreamClient (стриминг, автореконнект, фильтрация пингов)
- AsyncWebSocketClient / WebSocketClient (соединение, отправка/получение, автореконнект, фильтрация пингов)
- Выброс OptionalDependencyError при отсутствии websockets
"""
from __future__ import annotations

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from chutils.exceptions import OptionalDependencyError
from chutils.http.streaming import (
    AsyncEventStreamClient,
    AsyncWebSocketClient,
    EventStreamClient,
    ServerSentEvent,
    WebSocketClient,
)


async def _async_lines(lines: list[bytes]):
    for line in lines:
        yield line


@pytest.mark.asyncio
async def test_async_event_stream_client_success() -> None:
    """AsyncEventStreamClient успешно считывает события SSE."""
    # Подготавливаем mock httpx response
    mock_lines = [
        b"id: 1",
        b"event: message",
        b"data: hello",
        b"",  # Конец первого события
        b"data: world",
        b"",  # Конец второго события
    ]

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.aiter_lines.side_effect = lambda: _async_lines(mock_lines)

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.stream = MagicMock()
    mock_client.stream.return_value.__aenter__.return_value = mock_response

    with patch("httpx.AsyncClient", return_value=mock_client):
        client = AsyncEventStreamClient("http://example.com/sse")
        events: list[ServerSentEvent] = []
        async with client:
            async for event in client:
                events.append(event)

    assert len(events) == 2
    assert events[0].id == "1"
    assert events[0].event == "message"
    assert events[0].data == "hello"

    assert events[1].id is None
    assert events[1].event is None
    assert events[1].data == "world"


@pytest.mark.asyncio
async def test_async_event_stream_client_filter_heartbeats() -> None:
    """AsyncEventStreamClient фильтрует пинги/комментарии по умолчанию."""
    mock_lines = [
        b": keepalive",  # Комментарий
        b"",             # Пустое событие (из-за комментария)
        b"data: hello",
        b"",
    ]

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.aiter_lines.side_effect = lambda: _async_lines(mock_lines)

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.stream = MagicMock()
    mock_client.stream.return_value.__aenter__.return_value = mock_response

    # С фильтрацией (по умолчанию)
    with patch("httpx.AsyncClient", return_value=mock_client):
        client = AsyncEventStreamClient("http://example.com/sse", filter_heartbeats=True)
        events: list[ServerSentEvent] = []
        async with client:
            async for event in client:
                events.append(event)

    assert len(events) == 1
    assert events[0].data == "hello"

    # Без фильтрации
    mock_response.aiter_lines.side_effect = lambda: _async_lines(mock_lines)
    with patch("httpx.AsyncClient", return_value=mock_client):
        client = AsyncEventStreamClient("http://example.com/sse", filter_heartbeats=False)
        events = []
        async with client:
            async for event in client:
                events.append(event)

    # Должен выдать 2 события (одно пустое/комментарий, другое с hello)
    assert len(events) == 2


@pytest.mark.asyncio
async def test_async_event_stream_client_reconnect() -> None:
    """AsyncEventStreamClient осуществляет автореконнект при разрыве."""
    import httpx

    # Первый запрос бросает ошибку, второй возвращает данные
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.aiter_lines.side_effect = lambda: _async_lines([b"data: ok", b""])

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.stream = MagicMock()
    # Сначала бросаем TransportError, затем возвращаем response
    mock_client.stream.side_effect = [
        httpx.TransportError("Connection lost"),
        mock_client.stream.return_value,
    ]
    mock_client.stream.return_value.__aenter__.return_value = mock_response

    # Стратегия реконнекта: 1 задержка в 0.001 секунд
    reconnect_strategy = [0.001]

    with patch("httpx.AsyncClient", return_value=mock_client), patch("asyncio.sleep") as mock_sleep:
        client = AsyncEventStreamClient(
            "http://example.com/sse", reconnect_strategy=reconnect_strategy
        )
        events: list[ServerSentEvent] = []
        async with client:
            async for event in client:
                events.append(event)

    assert len(events) == 1
    assert events[0].data == "ok"
    mock_sleep.assert_called_once_with(0.001)


def test_sync_event_stream_client_success() -> None:
    """EventStreamClient (синхронный) успешно считывает события SSE."""
    mock_lines = [
        "id: 1",
        "event: message",
        "data: hello",
        "",
    ]

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.iter_lines.return_value = mock_lines

    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.stream.return_value.__enter__.return_value = mock_response

    with patch("httpx.Client", return_value=mock_client):
        client = EventStreamClient("http://example.com/sse")
        events: list[ServerSentEvent] = []
        with client:
            for event in client:
                events.append(event)

    assert len(events) == 1
    assert events[0].data == "hello"


# ─── WebSockets Tests ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_async_websocket_client_success() -> None:
    """AsyncWebSocketClient отправляет и получает сообщения."""
    mock_ws = AsyncMock()
    mock_ws.recv.side_effect = ["hello", "world"]

    # Имитируем websockets.connect
    with patch("websockets.connect", AsyncMock(return_value=mock_ws)) as mock_connect:
        client = AsyncWebSocketClient("ws://example.com/ws")
        async with client as ws:
            await ws.send("test")
            msg1 = await ws.recv()
            msg2 = await ws.recv()

    mock_connect.assert_called_once()
    mock_ws.send.assert_called_once_with("test")
    assert msg1 == "hello"
    assert msg2 == "world"


@pytest.mark.asyncio
async def test_async_websocket_client_reconnect() -> None:
    """AsyncWebSocketClient автоматически переподключается при разрыве."""
    import websockets.exceptions

    mock_ws = AsyncMock()
    mock_ws.recv.side_effect = [
        websockets.exceptions.ConnectionClosed(None, None),
        "recovered",
    ]

    # Сначала connect возвращает одно соединение, затем другое (или то же самое с восстановленным поведением)
    with patch("websockets.connect", AsyncMock(return_value=mock_ws)), patch("asyncio.sleep") as mock_sleep:
        client = AsyncWebSocketClient("ws://example.com/ws", reconnect_strategy=[0.001])
        async with client as ws:
            msg = await ws.recv()

    assert msg == "recovered"
    mock_sleep.assert_called_once_with(0.001)


def test_sync_websocket_client_success() -> None:
    """WebSocketClient (синхронный) отправляет и получает сообщения."""
    # Используем async mock в основе, но оборачиваем в синхронный интерфейс через event loop
    mock_ws = MagicMock()
    mock_ws.recv.return_value = "sync-response"

    # Будем мокать websockets.sync.client.connect
    with patch("websockets.sync.client.connect", return_value=mock_ws) as mock_connect:
        client = WebSocketClient("ws://example.com/ws")
        with client as ws:
            ws.send("hello-sync")
            msg = ws.recv()

    mock_connect.assert_called_once()
    mock_ws.send.assert_called_once_with("hello-sync")
    assert msg == "sync-response"


# ─── Dependency and Fallback Tests ──────────────────────────────────────────


def test_websocket_client_missing_dependency() -> None:
    """Выбрасывает OptionalDependencyError, если websockets не установлен."""
    # Подменяем sys.modules, чтобы имитировать отсутствие websockets
    with patch.dict("sys.modules", {"websockets": None}):
        with pytest.raises(OptionalDependencyError) as exc_info:
            AsyncWebSocketClient("ws://example.com/ws")
        assert "websockets" in str(exc_info.value)

        with pytest.raises(OptionalDependencyError) as exc_info:
            WebSocketClient("ws://example.com/ws")
        assert "websockets" in str(exc_info.value)


# ─── Additional Edge Case and Coverage Tests ───────────────────────────────


def test_default_backoff_generator() -> None:
    """Проверяет работу генератора экспоненциального бэкоффа по умолчанию."""
    from chutils.http.streaming import default_backoff
    gen = default_backoff(base_delay=0.1, max_delay=1.0, factor=2.0)
    delays = [next(gen) for _ in range(5)]
    # Каждый delay должен быть меньше или равен соответствующему экспоненциальному значению
    # 0.1, 0.2, 0.4, 0.8, 1.0
    assert delays[0] <= 0.1
    assert delays[1] <= 0.2
    assert delays[2] <= 0.4
    assert delays[3] <= 0.8
    assert delays[4] <= 1.0


def test_sse_parser_corner_cases() -> None:
    """Проверяет редкие и пограничные случаи парсинга SSE."""
    from chutils.http.streaming import SSEParser

    parser = SSEParser()
    # Неверный retry (нечисловой) должен игнорироваться
    assert parser.feed_line("retry: abc") is None
    assert parser.current_retry is None

    # Пустая строка/комментарий
    assert parser.feed_line(": heartbeat ping") is None

    # Поле без двоеточия
    assert parser.feed_line("data") is None
    assert parser.current_data == [""]

    # Завершение сообщения
    event = parser.feed_line("")
    assert event is not None
    assert event.data == ""


@pytest.mark.asyncio
async def test_async_websocket_iterator() -> None:
    """AsyncWebSocketClient поддерживает асинхронное итерирование (async for)."""
    mock_ws = AsyncMock()
    mock_ws.recv.side_effect = ["msg1", "msg2", Exception("End of stream")]

    with patch("websockets.connect", AsyncMock(return_value=mock_ws)):
        client = AsyncWebSocketClient("ws://example.com/ws", reconnect_strategy=[0.001])
        received = []
        try:
            async with client as ws:
                async for msg in ws:
                    received.append(msg)
        except Exception:
            pass

    assert received == ["msg1", "msg2"]


def test_sync_websocket_iterator() -> None:
    """WebSocketClient поддерживает синхронное итерирование (for in)."""
    mock_ws = MagicMock()
    mock_ws.recv.side_effect = ["sync1", "sync2", Exception("End of stream")]

    with patch("websockets.sync.client.connect", return_value=mock_ws):
        client = WebSocketClient("ws://example.com/ws", reconnect_strategy=[0.001])
        received = []
        try:
            with client as ws:
                for msg in ws:
                    received.append(msg)
        except Exception:
            pass

    assert received == ["sync1", "sync2"]


@pytest.mark.asyncio
async def test_async_websocket_reconnect_failure() -> None:
    """AsyncWebSocketClient выбрасывает ошибку, если стратегия реконнекта исчерпана."""
    import websockets.exceptions

    mock_ws = AsyncMock()
    mock_ws.recv.side_effect = websockets.exceptions.ConnectionClosed(None, None)

    # Пустая стратегия reconnect_strategy=[] означает, что реконнект делать нельзя
    with patch("websockets.connect", AsyncMock(return_value=mock_ws)):
        client = AsyncWebSocketClient("ws://example.com/ws", reconnect_strategy=[])
        async with client as ws:
            with pytest.raises(websockets.exceptions.ConnectionClosed):
                await ws.recv()


def test_sync_websocket_reconnect_failure() -> None:
    """WebSocketClient выбрасывает ошибку, если стратегия реконнекта исчерпана."""
    import websockets.exceptions

    mock_ws = MagicMock()
    mock_ws.recv.side_effect = websockets.exceptions.ConnectionClosed(None, None)

    with patch("websockets.sync.client.connect", return_value=mock_ws):
        client = WebSocketClient("ws://example.com/ws", reconnect_strategy=[])
        with client as ws:
            with pytest.raises(websockets.exceptions.ConnectionClosed):
                ws.recv()


@pytest.mark.asyncio
async def test_async_event_stream_client_default_backoff() -> None:
    """AsyncEventStreamClient может использовать бэкофф по умолчанию."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.aiter_lines.side_effect = lambda: _async_lines([b"data: default-backoff", b""])

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.stream = MagicMock()
    mock_client.stream.return_value.__aenter__.return_value = mock_response

    # Подменяем default_backoff на быстрый бэкофф, чтобы не ждать секунды
    from chutils.http.streaming import default_backoff
    with patch("httpx.AsyncClient", return_value=mock_client), patch(
        "chutils.http.streaming.default_backoff",
        return_value=iter([0.001])
    ):
        client = AsyncEventStreamClient("http://example.com/sse")
        async with client:
            events = [e async for e in client]

    assert len(events) == 1
    assert events[0].data == "default-backoff"

