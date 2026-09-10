"""Тесты локального асинхронного туннеля авторизации прокси (AsyncProxyTunnel)."""

import asyncio
from typing import Any

import pytest

from chutils.scraping.proxy.models import ProxyConfig
from chutils.scraping.proxy.tunnel import AsyncProxyTunnel


@pytest.mark.asyncio
async def test_async_proxy_tunnel_connect_auth_injection() -> None:
    """Проверяет корректный перехват CONNECT и инъекцию заголовка Proxy-Authorization."""
    received_headers: list[str] = []

    # Создаем mock upstream прокси-сервер
    async def mock_upstream_handler(
        reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        data = await reader.readuntil(b"\r\n\r\n")
        received_headers.append(data.decode("utf-8", errors="ignore"))

        # Отвечаем, что туннель установлен
        writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
        await writer.drain()

        # Эхо-обмен
        payload = await reader.read(4)
        if payload == b"PING":
            writer.write(b"PONG")
            await writer.drain()

        writer.close()
        await writer.wait_closed()

    upstream_server = await asyncio.start_server(
        mock_upstream_handler, "127.0.0.1", 0
    )
    upstream_port = upstream_server.sockets[0].getsockname()[1]

    proxy_cfg = ProxyConfig(
        host="127.0.0.1",
        port=upstream_port,
        protocol="http",
        username="test_user",
        password="test_secret_password",
    )

    tunnel = AsyncProxyTunnel(proxy=proxy_cfg, local_host="127.0.0.1", local_port=0)
    await tunnel.start()

    try:
        assert tunnel.port > 0
        assert tunnel.local_url == f"http://127.0.0.1:{tunnel.port}"
        assert tunnel.to_chrome_arg() == f"--proxy-server=http://127.0.0.1:{tunnel.port}"
        assert tunnel.to_proxy_config().port == tunnel.port

        # Подключаемся клиентом к локальному туннелю БЕЗ авторизации
        client_reader, client_writer = await asyncio.open_connection(
            "127.0.0.1", tunnel.port
        )
        # Отправляем CONNECT запрос
        client_writer.write(
            b"CONNECT target-site.org:443 HTTP/1.1\r\nHost: target-site.org:443\r\n\r\n"
        )
        await client_writer.drain()

        resp = await client_reader.readuntil(b"\r\n\r\n")
        assert b"200" in resp

        # Отправляем payload в туннель
        client_writer.write(b"PING")
        await client_writer.drain()

        reply = await client_reader.read(4)
        assert reply == b"PONG"

        client_writer.close()
        await client_writer.wait_closed()

        # Проверяем, что в upstream пришел заголовок Proxy-Authorization
        assert len(received_headers) == 1
        raw_headers = received_headers[0]
        assert "Proxy-Authorization: Basic " in raw_headers
        assert proxy_cfg.basic_auth_header is not None
        assert proxy_cfg.basic_auth_header in raw_headers

    finally:
        await tunnel.stop()
        upstream_server.close()
        await upstream_server.wait_closed()


@pytest.mark.asyncio
async def test_async_proxy_tunnel_context_manager() -> None:
    """Проверяет запуск и остановку туннеля через асинхронный контекстный менеджер."""
    proxy_cfg = ProxyConfig(host="127.0.0.1", port=9999, protocol="http")
    async with AsyncProxyTunnel(proxy=proxy_cfg) as tunnel:
        assert tunnel.is_running
        assert tunnel.port > 0

    assert not tunnel.is_running


@pytest.mark.asyncio
async def test_async_proxy_tunnel_socks5_upstream() -> None:
    """Проверяет работу туннеля с удаленным SOCKS5 прокси с аутентификацией."""
    socks_auth_checked = False

    async def mock_socks5_handler(
        reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        nonlocal socks_auth_checked
        # 1. Greeting
        greeting = await reader.readexactly(3)
        assert greeting[0] == 0x05
        writer.write(b"\x05\x02")  # method 2 (username/password)
        await writer.drain()

        # 2. Auth
        ver = (await reader.readexactly(1))[0]
        assert ver == 0x01
        u_len = (await reader.readexactly(1))[0]
        u = (await reader.readexactly(u_len)).decode()
        p_len = (await reader.readexactly(1))[0]
        p = (await reader.readexactly(p_len)).decode()
        assert u == "socks_user"
        assert p == "socks_pass"
        socks_auth_checked = True

        writer.write(b"\x01\x00")  # auth success
        await writer.drain()

        # 3. Connect
        req = await reader.readexactly(4)
        assert req[1] == 0x01  # CONNECT
        assert req[3] == 0x03  # Domain
        d_len = (await reader.readexactly(1))[0]
        domain = (await reader.readexactly(d_len)).decode()
        port = int.from_bytes(await reader.readexactly(2), "big")
        assert domain == "example.com"
        assert port == 443

        # Reply: success (BND.ADDR = 127.0.0.1:0)
        writer.write(b"\x05\x00\x00\x01\x7f\x00\x00\x01\x00\x00")
        await writer.drain()

        # Echo data
        data = await reader.read(4)
        if data == b"TEST":
            writer.write(b"OKAY")
            await writer.drain()

        writer.close()
        await writer.wait_closed()

    socks_server = await asyncio.start_server(mock_socks5_handler, "127.0.0.1", 0)
    socks_port = socks_server.sockets[0].getsockname()[1]

    proxy_cfg = ProxyConfig(
        host="127.0.0.1",
        port=socks_port,
        protocol="socks5",
        username="socks_user",
        password="socks_pass",
    )

    tunnel = AsyncProxyTunnel(proxy=proxy_cfg)
    await tunnel.start()

    try:
        # Клиент шлет CONNECT example.com:443 в HTTP туннель
        client_reader, client_writer = await asyncio.open_connection(
            "127.0.0.1", tunnel.port
        )
        client_writer.write(
            b"CONNECT example.com:443 HTTP/1.1\r\nHost: example.com:443\r\n\r\n"
        )
        await client_writer.drain()

        resp = await client_reader.readuntil(b"\r\n\r\n")
        assert b"200" in resp

        client_writer.write(b"TEST")
        await client_writer.drain()

        reply = await client_reader.read(4)
        assert reply == b"OKAY"
        assert socks_auth_checked

        client_writer.close()
        await client_writer.wait_closed()
    finally:
        await tunnel.stop()
        socks_server.close()
        await socks_server.wait_closed()

