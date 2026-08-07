"""
chutils.http.streaming — Модуль для поддержки HTTP-стриминга (SSE/Chunked) и WebSockets.
"""  # chutils: ignore[CodeDecompositionRule]
from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass
from types import TracebackType
from typing import Any, AsyncIterator, Callable, Iterable, Iterator

import httpx  # chutils: ignore[ChutilsIntegrationRule]

from chutils.exceptions import OptionalDependencyError


@dataclass
class ServerSentEvent:
    """Представляет собой отдельное событие Server-Sent Events (SSE)."""
    id: str | None = None
    event: str | None = None
    data: str = ""
    retry: int | None = None
    raw: str = ""


def default_backoff(
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    factor: float = 2.0,
) -> Iterator[float]:
    """Генератор экспоненциального бэкоффа с джиттером.

    Args:
        base_delay: Начальная задержка в секундах.
        max_delay: Максимальная задержка в секундах.
        factor: Множитель экспоненциального роста.

    Returns:
        Итератор с функциями задержки в секундах.
    """
    delay = base_delay
    while True:
        # Full Jitter
        jittered_delay = random.uniform(0, min(max_delay, delay))
        yield jittered_delay
        delay *= factor


def _check_websockets() -> None:
    """Проверяет наличие установленной библиотеки websockets."""
    try:
        import websockets  # noqa: F401
        import websockets.sync.client  # noqa: F401
    except ImportError:
        raise OptionalDependencyError(
            "Для работы с WebSockets необходимо установить chutils[websockets].\n"
            "Вы можете установить ее с помощью: pip install chutils[websockets] или uv add websockets"
        )


class SSEParser:
    """Парсер для Server-Sent Events."""

    def __init__(self) -> None:
        self.current_id: str | None = None
        self.current_event: str | None = None
        self.current_data: list[str] = []
        self.current_retry: int | None = None
        self.current_lines: list[str] = []

    def feed_line(self, line: str) -> ServerSentEvent | None:
        """Передает очередную строку в парсер SSE.

        Args:
            line: Входная строка данных SSE.

        Returns:
            Завершенное событие ServerSentEvent или None.
        """
        self.current_lines.append(line)
        if not line.strip():
            if not self.current_data and not self.current_id and not self.current_event and not self.current_retry:
                raw = "\n".join(self.current_lines)
                self.current_lines = []
                return ServerSentEvent(raw=raw)

            data = "\n".join(self.current_data)
            raw = "\n".join(self.current_lines)
            event = ServerSentEvent(
                id=self.current_id,
                event=self.current_event,
                data=data,
                retry=self.current_retry,
                raw=raw,
            )
            self.current_id = None
            self.current_event = None
            self.current_data = []
            self.current_retry = None
            self.current_lines = []
            return event

        if line.startswith(":"):
            return None

        if ":" in line:
            field, value = line.split(":", 1)
            value = value.lstrip()
        else:
            field = line
            value = ""

        if field == "data":
            self.current_data.append(value)
        elif field == "id":
            self.current_id = value
        elif field == "event":
            self.current_event = value
        elif field == "retry":
            try:
                self.current_retry = int(value)
            except ValueError:
                pass
        return None


class AsyncEventStreamClient:
    """Асинхронный клиент для HTTP Streaming и SSE."""

    def __init__(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
        filter_heartbeats: bool = True,
        reconnect_strategy: Iterable[float] | Callable[[], Iterable[float]] | None = None,
    ) -> None:
        self.url = url
        self.headers = headers or {}
        self.timeout = timeout
        self.filter_heartbeats = filter_heartbeats
        self._reconnect_strategy_input = reconnect_strategy
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> AsyncEventStreamClient:
        self._client = httpx.AsyncClient(timeout=self.timeout)
        await self._client.__aenter__()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if self._client:
            await self._client.__aexit__(exc_type, exc_val, exc_tb)
            self._client = None

    async def __aiter__(self) -> AsyncIterator[ServerSentEvent]:
        if self._reconnect_strategy_input is None:
            delay_iter = default_backoff()
        elif callable(self._reconnect_strategy_input):
            delay_iter = iter(self._reconnect_strategy_input())
        else:
            delay_iter = iter(self._reconnect_strategy_input)

        parser = SSEParser()

        while True:
            try:
                client_created = False
                if self._client is None:
                    self._client = httpx.AsyncClient(timeout=self.timeout)
                    await self._client.__aenter__()
                    client_created = True

                async with self._client.stream("GET", self.url, headers=self.headers) as response:
                    response.raise_for_status()

                    if self._reconnect_strategy_input is None:
                        delay_iter = default_backoff()

                    async for line_bytes in response.aiter_lines():
                        line = line_bytes
                        if isinstance(line, bytes):
                            line = line.decode("utf-8")

                        is_comment = line.startswith(":")
                        if self.filter_heartbeats and is_comment:
                            continue

                        event = parser.feed_line(line)
                        if event is not None:
                            is_empty = not event.data and not event.id and not event.event
                            if self.filter_heartbeats and is_empty:
                                continue
                            yield event

                break
            except (httpx.HTTPError, Exception) as exc:
                try:
                    delay = next(delay_iter)
                except StopIteration:
                    raise exc

                await asyncio.sleep(delay)
            finally:
                if 'client_created' in locals() and client_created and self._client:
                    await self._client.__aexit__(None, None, None)
                    self._client = None


class EventStreamClient:
    """Синхронный клиент-обертка для HTTP Streaming и SSE."""

    def __init__(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
        filter_heartbeats: bool = True,
        reconnect_strategy: Iterable[float] | Callable[[], Iterable[float]] | None = None,
    ) -> None:
        self.url = url
        self.headers = headers or {}
        self.timeout = timeout
        self.filter_heartbeats = filter_heartbeats
        self._reconnect_strategy_input = reconnect_strategy
        self._client: httpx.Client | None = None

    def __enter__(self) -> EventStreamClient:
        self._client = httpx.Client(timeout=self.timeout)
        self._client.__enter__()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if self._client:
            self._client.__exit__(exc_type, exc_val, exc_tb)
            self._client = None

    def __iter__(self) -> Iterator[ServerSentEvent]:
        if self._reconnect_strategy_input is None:
            delay_iter = default_backoff()
        elif callable(self._reconnect_strategy_input):
            delay_iter = iter(self._reconnect_strategy_input())
        else:
            delay_iter = iter(self._reconnect_strategy_input)

        parser = SSEParser()

        while True:
            try:
                client_created = False
                if self._client is None:
                    self._client = httpx.Client(timeout=self.timeout)
                    self._client.__enter__()
                    client_created = True

                with self._client.stream("GET", self.url, headers=self.headers) as response:
                    response.raise_for_status()

                    if self._reconnect_strategy_input is None:
                        delay_iter = default_backoff()

                    for line in response.iter_lines():
                        if isinstance(line, bytes):
                            line = line.decode("utf-8")

                        is_comment = line.startswith(":")
                        if self.filter_heartbeats and is_comment:
                            continue

                        event = parser.feed_line(line)
                        if event is not None:
                            is_empty = not event.data and not event.id and not event.event
                            if self.filter_heartbeats and is_empty:
                                continue
                            yield event

                break
            except (httpx.HTTPError, Exception) as exc:
                try:
                    delay = next(delay_iter)
                except StopIteration:
                    raise exc

                time.sleep(delay)
            finally:
                if 'client_created' in locals() and client_created and self._client:
                    self._client.__exit__(None, None, None)
                    self._client = None


class AsyncWebSocketClient:
    """Асинхронный клиент для WebSockets."""

    def __init__(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        filter_heartbeats: bool = True,
        reconnect_strategy: Iterable[float] | Callable[[], Iterable[float]] | None = None,
    ) -> None:
        _check_websockets()
        self.url = url
        self.headers = headers or {}
        self.filter_heartbeats = filter_heartbeats
        self._reconnect_strategy_input = reconnect_strategy
        self._websocket: Any = None
        self._delay_iter: Iterator[float] | None = None

    def _reset_reconnect_strategy(self) -> None:
        if self._reconnect_strategy_input is None:
            self._delay_iter = default_backoff()
        elif callable(self._reconnect_strategy_input):
            self._delay_iter = iter(self._reconnect_strategy_input())
        else:
            self._delay_iter = iter(self._reconnect_strategy_input)

    async def connect(self) -> None:
        """Устанавливает асинхронное соединение по WebSocket."""
        import websockets
        self._websocket = await websockets.connect(self.url, extra_headers=self.headers)
        if self._delay_iter is None:
            self._reset_reconnect_strategy()

    async def __aenter__(self) -> AsyncWebSocketClient:
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if self._websocket:
            await self._websocket.close()
            self._websocket = None

    async def send(self, message: str | bytes) -> None:
        """Отправляет текстовое или бинарное сообщение через WebSocket.

        Args:
            message: Сообщение для отправки.
        """
        import websockets.exceptions
        while True:
            try:
                if self._websocket is None:
                    await self.connect()
                await self._websocket.send(message)
                return
            except (websockets.exceptions.ConnectionClosed, OSError) as exc:
                await self._handle_reconnect(exc)

    async def recv(self) -> str | bytes:
        """Принимает текстовое или бинарное сообщение из WebSocket.

        Returns:
            Принятое сообщение.
        """
        import websockets.exceptions
        while True:
            try:
                if self._websocket is None:
                    await self.connect()
                msg: str | bytes = await self._websocket.recv()
                if self.filter_heartbeats and (msg == "" or msg == b""):
                    continue
                if self._reconnect_strategy_input is None:
                    self._reset_reconnect_strategy()
                return msg
            except (websockets.exceptions.ConnectionClosed, OSError) as exc:
                await self._handle_reconnect(exc)

    async def _handle_reconnect(self, exc: Exception) -> None:
        if self._delay_iter is None:
            self._reset_reconnect_strategy()

        assert self._delay_iter is not None
        try:
            delay = next(self._delay_iter)
        except StopIteration:
            raise exc

        await asyncio.sleep(delay)

        if self._websocket:
            try:
                await self._websocket.close()
            except Exception:
                pass
            self._websocket = None

        await self.connect()

    def __aiter__(self) -> AsyncIterator[str | bytes]:
        return self

    async def __anext__(self) -> str | bytes:
        try:
            return await self.recv()
        except Exception as exc:
            raise StopAsyncIteration from exc


class WebSocketClient:
    """Синхронный клиент-обертка для WebSockets."""

    def __init__(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        filter_heartbeats: bool = True,
        reconnect_strategy: Iterable[float] | Callable[[], Iterable[float]] | None = None,
    ) -> None:
        _check_websockets()
        self.url = url
        self.headers = headers or {}
        self.filter_heartbeats = filter_heartbeats
        self._reconnect_strategy_input = reconnect_strategy
        self._websocket: Any = None
        self._delay_iter: Iterator[float] | None = None

    def _reset_reconnect_strategy(self) -> None:
        if self._reconnect_strategy_input is None:
            self._delay_iter = default_backoff()
        elif callable(self._reconnect_strategy_input):
            self._delay_iter = iter(self._reconnect_strategy_input())
        else:
            self._delay_iter = iter(self._reconnect_strategy_input)

    def connect(self) -> None:
        """Устанавливает синхронное соединение по WebSocket."""
        import websockets.sync.client
        self._websocket = websockets.sync.client.connect(
            self.url, additional_headers=self.headers
        )
        if self._delay_iter is None:
            self._reset_reconnect_strategy()

    def __enter__(self) -> WebSocketClient:
        self.connect()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if self._websocket:
            self._websocket.close()
            self._websocket = None

    def send(self, message: str | bytes) -> None:
        """Отправляет текстовое или бинарное сообщение через WebSocket.

        Args:
            message: Сообщение для отправки.
        """
        import websockets.exceptions
        while True:
            try:
                if self._websocket is None:
                    self.connect()
                self._websocket.send(message)
                return
            except (websockets.exceptions.ConnectionClosed, OSError) as exc:
                self._handle_reconnect(exc)

    def recv(self) -> str | bytes:
        """Принимает текстовое или бинарное сообщение из WebSocket.

        Returns:
            Принятое сообщение.
        """
        import websockets.exceptions
        while True:
            try:
                if self._websocket is None:
                    self.connect()
                msg: str | bytes = self._websocket.recv()
                if self.filter_heartbeats and (msg == "" or msg == b""):
                    continue
                if self._reconnect_strategy_input is None:
                    self._reset_reconnect_strategy()
                return msg
            except (websockets.exceptions.ConnectionClosed, OSError) as exc:
                self._handle_reconnect(exc)

    def _handle_reconnect(self, exc: Exception) -> None:
        if self._delay_iter is None:
            self._reset_reconnect_strategy()

        assert self._delay_iter is not None
        try:
            delay = next(self._delay_iter)
        except StopIteration:
            raise exc

        time.sleep(delay)

        if self._websocket:
            try:
                self._websocket.close()
            except Exception:
                pass
            self._websocket = None

        self.connect()

    def __iter__(self) -> Iterator[str | bytes]:
        return self

    def __next__(self) -> str | bytes:
        try:
            return self.recv()
        except Exception as exc:
            raise StopIteration from exc
