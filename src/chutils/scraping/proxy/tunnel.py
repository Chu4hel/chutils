"""Локальный асинхронный туннель-прокси с автоматической инъекцией учетных данных."""

import asyncio
from types import TracebackType

from typing_extensions import Self

from chutils.logger import setup_logger
from chutils.scraping.proxy.models import ProxyConfig
from chutils.scraping.proxy.parser import parse_proxy

logger = setup_logger(__name__)


class AsyncProxyTunnel:
    """Локальный асинхронный HTTP/CONNECT форвардер для авторизации в удаленных прокси.

    Позволяет запускать Chromium или браузеры в headless-режимах без расширений,
    направляя трафик на локальный адрес `127.0.0.1:<port>`. Туннель прозрачно
    перехватывает запросы и добавляет заголовок `Proxy-Authorization` в удаленный прокси.
    """

    def __init__(
        self,
        proxy: ProxyConfig | str,
        local_host: str = "127.0.0.1",
        local_port: int = 0,
    ) -> None:
        """Инициализирует туннель.

        Args:
            proxy: Удаленный прокси-сервер (ProxyConfig или строка).
            local_host: Локальный адрес для прослушивания (по умолчанию 127.0.0.1).
            local_port: Локальный порт для прослушивания (0 для выбора свободного порта).
        """
        self.proxy: ProxyConfig = parse_proxy(proxy)
        self.local_host: str = local_host
        self.local_port: int = local_port
        self._server: asyncio.Server | None = None
        self._actual_port: int = 0
        self._active_tasks: set[asyncio.Task[None]] = set()

    @property
    def is_running(self) -> bool:
        """Проверяет, запущен ли локальный сервер туннеля."""
        return self._server is not None and self._server.is_serving()

    @property
    def host(self) -> str:
        """Возвращает локальный хост прослушивания."""
        return self.local_host

    @property
    def port(self) -> int:
        """Возвращает фактический локальный порт туннеля."""
        return self._actual_port

    @property
    def local_url(self) -> str:
        """Возвращает локальный HTTP URL туннеля."""
        return f"http://{self.host}:{self.port}"

    def to_proxy_config(self) -> ProxyConfig:
        """Возвращает конфигурацию локального прокси без авторизации.

        Returns:
            Экземпляр ProxyConfig для подключения к локальному туннелю.
        """
        return ProxyConfig(protocol="http", host=self.host, port=self.port)

    def to_chrome_arg(self) -> str:
        """Возвращает флаг командной строки --proxy-server для запуска Chromium.

        Returns:
            Строка флага --proxy-server с локальным адресом туннеля.
        """
        return f"--proxy-server=http://{self.host}:{self.port}"

    async def start(self) -> Self:
        """Запускает локальный сервер прокси-туннеля.

        Returns:
            Экземпляр туннеля.
        """
        if self.is_running:
            return self

        self._server = await asyncio.start_server(
            self._handle_client,
            host=self.local_host,
            port=self.local_port,
        )
        sockets = self._server.sockets
        if sockets:
            self._actual_port = sockets[0].getsockname()[1]
        logger.debug(
            "Запущен локальный прокси-туннель на %s:%d -> %s",
            self.host,
            self.port,
            self.proxy.masked_url,
        )
        return self

    async def stop(self) -> None:
        """Останавливает локальный сервер туннеля и завершает активные соединения."""
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

        if self._active_tasks:
            for task in list(self._active_tasks):
                task.cancel()
            await asyncio.gather(*self._active_tasks, return_exceptions=True)
            self._active_tasks.clear()

        logger.debug("Остановлен локальный прокси-туннель на порту %d", self.port)

    async def _handle_client(
        self, client_reader: asyncio.StreamReader, client_writer: asyncio.StreamWriter
    ) -> None:
        """Обрабатывает входящее соединение от клиента (браузера)."""
        current_task = asyncio.current_task()
        if current_task is not None:
            self._active_tasks.add(current_task)
            current_task.add_done_callback(self._active_tasks.discard)

        try:
            # Читаем заголовки запроса до разделителя \r\n\r\n
            try:
                header_bytes = await client_reader.readuntil(b"\r\n\r\n")
            except (asyncio.IncompleteReadError, ConnectionResetError):
                client_writer.close()
                await client_writer.wait_closed()
                return

            header_text = header_bytes.decode("iso-8859-1")
            request_line = header_text.split("\r\n", 1)[0]
            parts = request_line.split()
            if len(parts) < 2:
                client_writer.close()
                await client_writer.wait_closed()
                return

            method = parts[0].upper()
            target = parts[1]

            if method == "CONNECT":
                await self._handle_connect(
                    target, client_reader, client_writer
                )
            else:
                await self._handle_http(
                    header_bytes, client_reader, client_writer
                )
        except (ConnectionResetError, BrokenPipeError, asyncio.CancelledError):
            pass
        except Exception as e:
            logger.debug("Ошибка в клиентском соединении туннеля: %s", e)
        finally:
            try:
                client_writer.close()
                await client_writer.wait_closed()
            except Exception:
                pass

    async def _handle_connect(
        self,
        target: str,
        client_reader: asyncio.StreamReader,
        client_writer: asyncio.StreamWriter,
    ) -> None:
        """Обрабатывает CONNECT запрос для HTTPS соединений."""
        try:
            remote_reader, remote_writer = await asyncio.open_connection(
                self.proxy.host, self.proxy.port
            )
        except Exception as e:
            logger.debug("Не удалось соединиться с удаленным прокси: %s", e)
            client_writer.write(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
            await client_writer.drain()
            return

        try:
            if self.proxy.protocol.startswith("socks"):
                # SOCKS5 Handshake
                await self._socks5_handshake(
                    remote_reader, remote_writer, target
                )
            else:
                # HTTP CONNECT Forwarding
                connect_req = f"CONNECT {target} HTTP/1.1\r\nHost: {target}\r\n"
                if self.proxy.has_auth and self.proxy.basic_auth_header:
                    connect_req += (
                        f"Proxy-Authorization: {self.proxy.basic_auth_header}\r\n"
                    )
                connect_req += "Proxy-Connection: keep-alive\r\n\r\n"
                remote_writer.write(connect_req.encode("iso-8859-1"))
                await remote_writer.drain()

                # Читаем ответ upstream прокси
                resp = await remote_reader.readuntil(b"\r\n\r\n")
                if not (resp.startswith(b"HTTP/1.1 200") or resp.startswith(b"HTTP/1.0 200")):
                    client_writer.write(resp)
                    await client_writer.drain()
                    remote_writer.close()
                    await remote_writer.wait_closed()
                    return

            # Подтверждаем клиенту успешное установление туннеля
            client_writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            await client_writer.drain()

            # Двунаправленная пересылка данных
            await asyncio.gather(
                self._pipe(client_reader, remote_writer),
                self._pipe(remote_reader, client_writer),
            )
        finally:
            try:
                remote_writer.close()
                await remote_writer.wait_closed()
            except Exception:
                pass

    async def _handle_http(
        self,
        initial_headers: bytes,
        client_reader: asyncio.StreamReader,
        client_writer: asyncio.StreamWriter,
    ) -> None:
        """Обрабатывает стандартные HTTP запросы (GET, POST и др.)."""
        try:
            remote_reader, remote_writer = await asyncio.open_connection(
                self.proxy.host, self.proxy.port
            )
        except Exception as e:
            logger.debug("Не удалось соединиться с удаленным прокси: %s", e)
            client_writer.write(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
            await client_writer.drain()
            return

        try:
            # Внедряем заголовок Proxy-Authorization, если настроена аутентификация
            modified_headers = initial_headers
            if self.proxy.has_auth and self.proxy.basic_auth_header:
                auth_hdr = (
                    f"Proxy-Authorization: {self.proxy.basic_auth_header}\r\n".encode(
                        "iso-8859-1"
                    )
                )
                idx = modified_headers.find(b"\r\n\r\n")
                if idx != -1:
                    modified_headers = (
                        modified_headers[:idx] + b"\r\n" + auth_hdr + b"\r\n"
                    )

            remote_writer.write(modified_headers)
            await remote_writer.drain()

            await asyncio.gather(
                self._pipe(client_reader, remote_writer),
                self._pipe(remote_reader, client_writer),
            )
        finally:
            try:
                remote_writer.close()
                await remote_writer.wait_closed()
            except Exception:
                pass

    async def _socks5_handshake(
        self,
        writer_reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        target: str,
    ) -> None:
        """Выполняет рукопожатие по протоколу SOCKS5 (RFC 1928 / RFC 1929)."""
        # 1. Приветствие SOCKS5
        if self.proxy.has_auth:
            writer.write(b"\x05\x01\x02")  # Версия 5, метод 0x02 (Username/Password)
        else:
            writer.write(b"\x05\x01\x00")  # Метод 0x00 (No Auth)
        await writer.drain()

        method_resp = await writer_reader.readexactly(2)
        if method_resp[0] != 0x05:
            raise ConnectionError(f"Некорректная версия SOCKS5: {method_resp[0]}")

        # 2. Аутентификация
        if method_resp[1] == 0x02:
            u_bytes = (self.proxy.username or "").encode("utf-8")
            p_bytes = (self.proxy.password or "").encode("utf-8")
            writer.write(
                b"\x01"
                + len(u_bytes).to_bytes(1, "big")
                + u_bytes
                + len(p_bytes).to_bytes(1, "big")
                + p_bytes
            )
            await writer.drain()

            auth_resp = await writer_reader.readexactly(2)
            if auth_resp[1] != 0x00:
                raise PermissionError("Ошибка аутентификации в SOCKS5 прокси")
        elif method_resp[1] != 0x00:
            raise ConnectionError(f"Неподдерживаемый метод аутентификации SOCKS5: {method_resp[1]}")

        # 3. Запрос CONNECT
        if ":" in target:
            h, p_str = target.rsplit(":", 1)
            t_port = int(p_str)
        else:
            h = target
            t_port = 80
        h_bytes = h.encode("utf-8")

        # CMD=1 (CONNECT), RSV=0, ATYP=3 (Domain name)
        writer.write(
            b"\x05\x01\x00\x03"
            + len(h_bytes).to_bytes(1, "big")
            + h_bytes
            + t_port.to_bytes(2, "big")
        )
        await writer.drain()

        # Ответ сервера: VER(1) + REP(1) + RSV(1) + ATYP(1) + BND.ADDR + BND.PORT(2)
        header = await writer_reader.readexactly(4)
        if header[1] != 0x00:
            raise ConnectionError(f"Ошибка SOCKS5 CONNECT, статус: {header[1]}")

        atyp = header[3]
        if atyp == 0x01:  # IPv4
            await writer_reader.readexactly(4 + 2)
        elif atyp == 0x03:  # Domain
            d_len = (await writer_reader.readexactly(1))[0]
            await writer_reader.readexactly(d_len + 2)
        elif atyp == 0x04:  # IPv6
            await writer_reader.readexactly(16 + 2)

    async def _pipe(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """Передает поток байтов из reader в writer до достижения EOF."""
        try:
            while not reader.at_eof():
                data = await reader.read(65536)
                if not data:
                    break
                writer.write(data)
                await writer.drain()
        except (ConnectionResetError, BrokenPipeError, asyncio.CancelledError):
            pass
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    async def __aenter__(self) -> Self:
        """Вход в асинхронный контекстный менеджер (запускает туннель).

        Returns:
            Экземпляр запущенного AsyncProxyTunnel.
        """
        await self.start()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Выход из асинхронного контекстного менеджера (останавливает туннель).

        Args:
            exc_type: Тип исключения.
            exc_val: Значение исключения.
            exc_tb: Трассировка стека.
        """
        await self.stop()
