"""Unit-тесты для применения антидетекта через WebDriver BiDi (apply_antidetect_bidi)."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import pytest
import websockets

from chutils.scraping.bidi import (
    BiDiClient,
    BiDiSession,
    apply_antidetect_bidi,
)
from chutils.scraping.humanize.config import AntidetectConfig


@asynccontextmanager
async def start_mock_bidi_preload_server() -> AsyncIterator[dict[str, Any]]:
    """Фиктивный сервер BiDi для тестирования preload-скриптов антидетекта."""
    recorded_commands: list[dict[str, Any]] = []

    async def handler(websocket: Any) -> None:
        try:
            async for message in websocket:
                data = json.loads(message)
                recorded_commands.append(data)
                cmd_id = data.get("id")
                method = data.get("method")

                if method == "script.addPreloadScript":
                    resp = {
                        "id": cmd_id,
                        "type": "success",
                        "result": {"script": "antidetect-script-token-123"},
                    }
                elif method == "browsingContext.getTree":
                    resp = {
                        "id": cmd_id,
                        "type": "success",
                        "result": {"contexts": [{"context": "ctx-default"}]},
                    }
                else:
                    resp = {"id": cmd_id, "type": "success", "result": {}}

                await websocket.send(json.dumps(resp))
        except websockets.exceptions.ConnectionClosed:
            pass

    server = await websockets.serve(handler, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    url = f"ws://127.0.0.1:{port}"

    try:
        yield {"url": url, "server": server, "commands": recorded_commands}
    finally:
        server.close()
        await server.wait_closed()


@pytest.mark.asyncio
async def test_apply_antidetect_bidi_with_session() -> None:
    """Проверяет вызов apply_antidetect_bidi с объектом BiDiSession."""
    async with start_mock_bidi_preload_server() as mock_bidi_preload_server:
        session = BiDiSession(mock_bidi_preload_server["url"])
        await session.start()

        try:
            script_id = await apply_antidetect_bidi(session)
            assert script_id == "antidetect-script-token-123"

            # Проверяем параметры вызова команды
            add_cmds = [
                c
                for c in mock_bidi_preload_server["commands"]
                if c.get("method") == "script.addPreloadScript"
            ]
            assert len(add_cmds) == 1
            fn_decl = add_cmds[0]["params"]["functionDeclaration"]
            assert fn_decl.startswith("() => {")
            assert "navigator" in fn_decl
            assert "webdriver" in fn_decl
        finally:
            await session.close()


@pytest.mark.asyncio
async def test_apply_antidetect_bidi_with_client() -> None:
    """Проверяет вызов apply_antidetect_bidi с объектом BiDiClient."""
    async with start_mock_bidi_preload_server() as mock_bidi_preload_server:
        client = BiDiClient(mock_bidi_preload_server["url"])
        await client.connect()

        try:
            script_id = await apply_antidetect_bidi(client)
            assert script_id == "antidetect-script-token-123"
        finally:
            await client.close()


@pytest.mark.asyncio
async def test_apply_antidetect_bidi_mobile_preset() -> None:
    """Проверяет интеграцию мобильного отпечатка с BiDi preload script."""
    async with start_mock_bidi_preload_server() as mock_bidi_preload_server:
        session = BiDiSession(mock_bidi_preload_server["url"])
        await session.start()

        try:
            cfg = AntidetectConfig.preset_mobile_android(device="pixel_8")
            script_id = await apply_antidetect_bidi(
                session,
                config=cfg,
                contexts=["ctx-tab-1"],
                sandbox="antidetect_sandbox",
            )
            assert script_id == "antidetect-script-token-123"

            add_cmds = [
                c
                for c in mock_bidi_preload_server["commands"]
                if c.get("method") == "script.addPreloadScript"
            ]
            params = add_cmds[-1]["params"]
            assert params.get("contexts") == ["ctx-tab-1"]
            assert params.get("sandbox") == "antidetect_sandbox"

            fn_decl = params["functionDeclaration"]
            # Должны присутствовать мобильные touch-патчи и Android
            assert "ontouchstart" in fn_decl
            assert "TouchEvent" in fn_decl
            assert "Mali-G715" in fn_decl
            assert "Android" in fn_decl
            assert "Pixel 8" in cfg.user_agent
        finally:
            await session.close()


@pytest.mark.asyncio
async def test_apply_antidetect_bidi_invalid_type() -> None:
    """Проверяет TypeError при передаче неподдерживаемого типа."""
    with pytest.raises(TypeError, match="Ожидался BiDiSession или BiDiClient"):
        await apply_antidetect_bidi("invalid_session")  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_apply_antidetect_bidi_browser_flavors() -> None:
    """Проверяет интеграцию preload-скриптов для браузеров Chromium и Firefox."""
    async with start_mock_bidi_preload_server() as mock_server:
        ws_url = mock_server["url"]

        # Имитация драйвера Chrome с BiDi capabilities
        class MockChromeDriver:
            def __init__(self) -> None:
                self.capabilities = {
                    "browserName": "chrome",
                    "browserVersion": "128.0",
                    "webSocketUrl": ws_url,
                }

        # Имитация драйвера Firefox / Gecko с BiDi capabilities
        class MockFirefoxDriver:
            def __init__(self) -> None:
                self.capabilities = {
                    "browserName": "firefox",
                    "browserVersion": "129.0",
                    "webSocketUrl": ws_url,
                }

        # 1. Chromium сессия
        session_chrome = BiDiSession(MockChromeDriver())
        await session_chrome.start()
        try:
            cfg_chrome = AntidetectConfig(webgl_vendor="Google Inc. (NVIDIA)")
            sid_chrome = await apply_antidetect_bidi(session_chrome, config=cfg_chrome)
            assert sid_chrome == "antidetect-script-token-123"
        finally:
            await session_chrome.close()

        # 2. Firefox сессия
        session_firefox = BiDiSession(MockFirefoxDriver())
        await session_firefox.start()
        try:
            cfg_firefox = AntidetectConfig(webgl_vendor="Mozilla")
            sid_firefox = await apply_antidetect_bidi(session_firefox, config=cfg_firefox)
            assert sid_firefox == "antidetect-script-token-123"
        finally:
            await session_firefox.close()
