"""Unit-тесты для клиента протокола WebDriver BiDi и сессий."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import pytest
import websockets

from chutils.scraping.bidi.client import BiDiClient
from chutils.scraping.bidi.exceptions import (
    BiDiCommandError,
    BiDiConnectionError,
    BiDiTimeoutError,
)
from chutils.scraping.bidi.session import bidi_session, extract_bidi_url


@asynccontextmanager
async def start_mock_bidi_server() -> AsyncIterator[dict[str, Any]]:
    """Запускает изолированный фиктивный WebSocket сервер WebDriver BiDi для теста."""
    received_commands: list[dict[str, Any]] = []
    connected_clients: list[Any] = []

    async def handler(websocket: Any) -> None:
        connected_clients.append(websocket)
        try:
            async for message in websocket:
                data = json.loads(message)
                received_commands.append(data)
                cmd_id = data.get("id")
                method = data.get("method")
                params = data.get("params", {})

                if method == "session.new":
                    resp = {
                        "id": cmd_id,
                        "type": "success",
                        "result": {"sessionId": "test-session-123", "capabilities": {}},
                    }
                elif method == "browsingContext.getTree":
                    resp = {
                        "id": cmd_id,
                        "type": "success",
                        "result": {
                            "contexts": [
                                {
                                    "context": "ctx-top-1",
                                    "url": "https://example.com",
                                    "children": [],
                                }
                            ]
                        },
                    }
                elif method == "browsingContext.navigate":
                    resp = {
                        "id": cmd_id,
                        "type": "success",
                        "result": {"navigation": "nav-456", "url": params.get("url")},
                    }
                elif method == "browsingContext.create":
                    resp = {
                        "id": cmd_id,
                        "type": "success",
                        "result": {"context": "ctx-new-tab"},
                    }
                elif method == "browsingContext.close":
                    resp = {"id": cmd_id, "type": "success", "result": {}}
                elif method == "script.evaluate":
                    resp = {
                        "id": cmd_id,
                        "type": "success",
                        "result": {
                            "type": "success",
                            "result": {"type": "string", "value": "eval_result_123"},
                        },
                    }
                elif method == "script.callFunction":
                    resp = {
                        "id": cmd_id,
                        "type": "success",
                        "result": {
                            "type": "success",
                            "result": {"type": "number", "value": 42},
                        },
                    }
                elif method == "script.addPreloadScript":
                    resp = {
                        "id": cmd_id,
                        "type": "success",
                        "result": {"script": "preload-script-uuid-999"},
                    }
                elif method == "script.removePreloadScript":
                    resp = {"id": cmd_id, "type": "success", "result": {}}
                elif method == "error.command":
                    resp = {
                        "id": cmd_id,
                        "type": "error",
                        "error": "invalid argument",
                        "message": "Custom test error message",
                    }
                elif method == "slow.command":
                    await asyncio.sleep(0.4)
                    resp = {"id": cmd_id, "type": "success", "result": {"status": "ok"}}
                else:
                    resp = {"id": cmd_id, "type": "success", "result": {}}

                await websocket.send(json.dumps(resp))
        except websockets.exceptions.ConnectionClosed:
            pass

    server = await websockets.serve(handler, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    url = f"ws://127.0.0.1:{port}"

    try:
        yield {
            "url": url,
            "server": server,
            "commands": received_commands,
            "clients": connected_clients,
        }
    finally:
        server.close()
        await server.wait_closed()


@pytest.mark.asyncio
async def test_bidi_client_connect_and_close() -> None:
    """Проверяет подключение и корректное закрытие клиента BiDiClient."""
    async with start_mock_bidi_server() as mock_bidi_server:
        client = BiDiClient(mock_bidi_server["url"])
        assert not client.is_connected

        await client.connect()
        assert client.is_connected

        await client.close()
        assert not client.is_connected


@pytest.mark.asyncio
async def test_bidi_client_connection_error() -> None:
    """Проверяет возникновение BiDiConnectionError при недоступном сервере."""
    client = BiDiClient("ws://127.0.0.1:59999")
    with pytest.raises(BiDiConnectionError):
        await client.connect()


@pytest.mark.asyncio
async def test_bidi_client_send_command_unconnected() -> None:
    """Проверяет ошибку отправки команды на неподключенном клиенте."""
    client = BiDiClient("ws://127.0.0.1:59999")
    with pytest.raises(BiDiConnectionError, match="BiDiClient не подключен"):
        await client.send_command("session.new")


@pytest.mark.asyncio
async def test_bidi_client_methods() -> None:
    """Проверяет вызовы высокоуровневых методов BiDi протокола."""
    async with start_mock_bidi_server() as mock_bidi_server:
        client = BiDiClient(mock_bidi_server["url"])
        await client.connect()

        try:
            # session.new
            res_session = await client.session_new()
            assert res_session.get("sessionId") == "test-session-123"

            # browsingContext.getTree
            contexts = await client.browsing_context_get_tree()
            assert len(contexts) == 1
            assert contexts[0]["context"] == "ctx-top-1"

            # browsingContext.navigate
            nav_res = await client.browsing_context_navigate(
                context="ctx-top-1", url="https://example.com/page"
            )
            assert nav_res.get("url") == "https://example.com/page"

            # browsingContext.create
            ctx_new = await client.browsing_context_create(type="tab")
            assert ctx_new.get("context") == "ctx-new-tab"

            # browsingContext.close
            close_res = await client.browsing_context_close(context="ctx-new-tab")
            assert isinstance(close_res, dict)

            # script.evaluate
            eval_res = await client.script_evaluate(
                expression="2 + 2", target={"context": "ctx-top-1"}
            )
            assert eval_res.get("result", {}).get("value") == "eval_result_123"

            # script.callFunction
            call_res = await client.script_call_function(
                function_declaration="() => 42", target={"context": "ctx-top-1"}
            )
            assert call_res.get("result", {}).get("value") == 42

            # script.addPreloadScript & removePreloadScript
            script_id = await client.script_add_preload_script(
                function_declaration="() => console.log('preload')"
            )
            assert script_id == "preload-script-uuid-999"

            rem_res = await client.script_remove_preload_script(script_id)
            assert isinstance(rem_res, dict)

        finally:
            await client.close()


@pytest.mark.asyncio
async def test_bidi_client_command_error() -> None:
    """Проверяет преобразование ошибки BiDi в BiDiCommandError."""
    async with start_mock_bidi_server() as mock_bidi_server:
        client = BiDiClient(mock_bidi_server["url"])
        await client.connect()

        try:
            with pytest.raises(BiDiCommandError) as exc_info:
                await client.send_command("error.command")

            assert exc_info.value.error_code == "invalid argument"
            assert "Custom test error message" in exc_info.value.message
        finally:
            await client.close()


@pytest.mark.asyncio
async def test_bidi_client_timeout() -> None:
    """Проверяет возникновение BiDiTimeoutError при превышении лимита времени."""
    async with start_mock_bidi_server() as mock_bidi_server:
        client = BiDiClient(mock_bidi_server["url"])
        await client.connect()

        try:
            with pytest.raises(BiDiTimeoutError):
                await client.send_command("slow.command", timeout=0.1)
        finally:
            await client.close()


@pytest.mark.asyncio
async def test_bidi_client_event_dispatch() -> None:
    """Проверяет подписку и диспетчеризацию событий браузера."""
    async with start_mock_bidi_server() as mock_bidi_server:
        client = BiDiClient(mock_bidi_server["url"])
        await client.connect()

        received_events: list[dict[str, Any]] = []

        def on_load(params: dict[str, Any]) -> None:
            received_events.append(params)

        async def on_async_load(params: dict[str, Any]) -> None:
            received_events.append({"async": True, **params})

        client.on("browsingContext.load", on_load)
        client.on("browsingContext.load", on_async_load)

        # Имитируем отправку события сервером
        event_payload = {
            "type": "event",
            "method": "browsingContext.load",
            "params": {"context": "ctx-top-1", "url": "https://example.com/loaded"},
        }
        server_client = mock_bidi_server["clients"][0]
        await server_client.send(json.dumps(event_payload))

        # Даем циклу событий время на обработку
        await asyncio.sleep(0.05)

        assert len(received_events) == 2
        assert received_events[0]["url"] == "https://example.com/loaded"
        assert received_events[1]["async"] is True

        # Проверка отписки
        client.remove_listener("browsingContext.load", on_load)
        await server_client.send(json.dumps(event_payload))
        await asyncio.sleep(0.05)

        assert len(received_events) == 3

        await client.close()


def test_extract_bidi_url() -> None:
    """Проверяет утилиту extract_bidi_url для различных источников."""
    # Прямой URL
    assert extract_bidi_url("ws://localhost:9222/bidi") == "ws://localhost:9222/bidi"
    assert extract_bidi_url("wss://remote:443/session") == "wss://remote:443/session"

    # Невалидная строка
    with pytest.raises(ValueError, match="Недопустимый протокол WebSocket URL"):
        extract_bidi_url("http://localhost:9222")

    # Объект с capabilities webSocketUrl (W3C BiDi)
    class MockDriverW3C:
        def __init__(self) -> None:
            self.capabilities = {"webSocketUrl": "ws://127.0.0.1:4444/session/123"}

    assert extract_bidi_url(MockDriverW3C()) == "ws://127.0.0.1:4444/session/123"

    # Объект с bidi_connection
    class MockDriverBidiConn:
        def __init__(self) -> None:
            self.bidi_connection = "ws://127.0.0.1:8888/bidi"

    assert extract_bidi_url(MockDriverBidiConn()) == "ws://127.0.0.1:8888/bidi"

    # Chrome options debuggerAddress
    class MockChromeDriver:
        def __init__(self) -> None:
            self.capabilities = {"goog:chromeOptions": {"debuggerAddress": "localhost:9222"}}

    assert (
        extract_bidi_url(MockChromeDriver())
        == "ws://localhost:9222/devtools/browser"
    )

    # Неподдерживаемый объект
    with pytest.raises(ValueError, match="Не удалось извлечь WebDriver BiDi WebSocket URL"):
        extract_bidi_url(object())


@pytest.mark.asyncio
async def test_bidi_session_context_manager() -> None:
    """Проверяет управление контекстом через bidi_session и BiDiSession."""
    async with start_mock_bidi_server() as mock_bidi_server:
        async with bidi_session(mock_bidi_server["url"]) as session:
            assert session.active_context_id == "ctx-top-1"

            # Навигация
            nav = await session.navigate("https://example.com/test")
            assert nav.get("url") == "https://example.com/test"

            # Evaluate value
            val = await session.evaluate_value("window.location.href")
            assert val == "eval_result_123"

            # Preload script
            sid = await session.add_preload_script("() => console.log('test')")
            assert sid == "preload-script-uuid-999"

            # New tab
            new_tab_id = await session.new_tab()
            assert new_tab_id == "ctx-new-tab"
            assert session.active_context_id == "ctx-new-tab"

            # Close tab
            await session.close_tab(new_tab_id)
