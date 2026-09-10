"""Локальный тестовый HTTP-сервер (песочница) для тестирования парсеров и браузеров."""

import json
import threading
import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import TracebackType
from typing import Any
from urllib.parse import urlparse

from typing_extensions import Self

from chutils.logger import setup_logger

logger = setup_logger(__name__)


@dataclass
class RecordedRequest:
    """Запись входящего HTTP-запроса от браузера или клиента."""

    method: str
    path: str
    headers: dict[str, str]
    body: bytes
    query: str


@dataclass
class TestResponse:
    """Ответ локального сервера на тестовый запрос клиента."""

    status: int
    headers: dict[str, str]
    content: bytes

    @property
    def text(self) -> str:
        """Возвращает декодированное текстовое содержимое ответа."""
        return self.content.decode("utf-8", errors="replace")

    def json(self) -> Any:
        """Десериализует JSON из тела ответа.

        Returns:
            Десериализованные данные (словарь, список или примитив).
        """
        return json.loads(self.text)


class _TestHandler(BaseHTTPRequestHandler):
    """Внутренний обработчик HTTP-запросов тестового сервера."""

    server: "_CustomHTTPServer"

    def do_GET(self) -> None:
        """Обрабатывает входящий HTTP GET запрос."""
        self._handle_request("GET")

    def do_POST(self) -> None:
        """Обрабатывает входящий HTTP POST запрос."""
        self._handle_request("POST")

    def do_HEAD(self) -> None:
        """Обрабатывает входящий HTTP HEAD запрос."""
        self._handle_request("HEAD")

    def do_PUT(self) -> None:
        """Обрабатывает входящий HTTP PUT запрос."""
        self._handle_request("PUT")

    def do_DELETE(self) -> None:
        """Обрабатывает входящий HTTP DELETE запрос."""
        self._handle_request("DELETE")

    def _handle_request(self, method: str) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        query = parsed.query

        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len) if content_len > 0 else b""

        headers_dict: dict[str, str] = {k: v for k, v in self.headers.items()}
        rec = RecordedRequest(
            method=method,
            path=path,
            headers=headers_dict,
            body=body,
            query=query,
        )
        self.server.owner.requests_log.append(rec)

        route_info = self.server.owner._routes.get(path)
        if route_info is not None:
            status_code, content_type, response_bytes = route_info
            self.send_response(status_code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(response_bytes)))
            self.end_headers()
            if method != "HEAD":
                self.wfile.write(response_bytes)
                self.wfile.flush()
        else:
            self.send_response(404)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            msg = b"404 Not Found"
            self.send_header("Content-Length", str(len(msg)))
            self.end_headers()
            if method != "HEAD":
                self.wfile.write(msg)
                self.wfile.flush()

    def log_message(self, format: str, *args: object) -> None:
        """Подавляет стандартный вывод BaseHTTPRequestHandler в stderr.

        Args:
            format: Строка формата сообщения.
            *args: Аргументы форматирования.
        """


class _CustomHTTPServer(ThreadingHTTPServer):
    """Расширение ThreadingHTTPServer со ссылкой на экземпляр LocalTestServer."""

    def __init__(
        self,
        server_address: tuple[str, int],
        RequestHandlerClass: type[BaseHTTPRequestHandler],
        owner: "LocalTestServer",
    ) -> None:
        super().__init__(server_address, RequestHandlerClass)
        self.owner: LocalTestServer = owner


class LocalTestServer:
    """Локальный тестовый HTTP-сервер песочницы для отдачи HTML/JSON браузерам в тестах."""

    def __init__(self, host: str = "127.0.0.1", port: int = 0) -> None:
        """Инициализирует сервер.

        Args:
            host: Хост прослушивания (по умолчанию 127.0.0.1).
            port: Порт (0 для авто-выбора свободного порта ОС).
        """
        self.host: str = host
        self._requested_port: int = port
        self._actual_port: int = 0
        self._httpd: _CustomHTTPServer | None = None
        self._thread: threading.Thread | None = None
        # path -> (status, content_type, bytes)
        self._routes: dict[str, tuple[int, str, bytes]] = {}
        self.requests_log: list[RecordedRequest] = []

    @property
    def is_running(self) -> bool:
        """Проверяет, запущен ли сервер."""
        return (
            self._httpd is not None
            and self._thread is not None
            and self._thread.is_alive()
        )

    @property
    def port(self) -> int:
        """Возвращает актуальный порт работающего сервера."""
        return self._actual_port

    def url_for(self, path: str) -> str:
        """Формирует абсолютный URL для указанного относительного пути.

        Args:
            path: Путь маршрута (например, '/page').

        Returns:
            Полный HTTP URL на локальном сервере.
        """
        clean_path = path if path.startswith("/") else f"/{path}"
        return f"http://{self.host}:{self.port}{clean_path}"

    def serve_html(
        self, path: str, html: str, content_type: str = "text/html; charset=utf-8"
    ) -> str:
        """Регистрирует HTML-маршрут.

        Args:
            path: Путь URL (например, '/index').
            html: HTML-содержимое.
            content_type: Заголовок Content-Type.

        Returns:
            Абсолютный URL зарегистрированного маршрута.
        """
        clean_path = path if path.startswith("/") else f"/{path}"
        self._routes[clean_path] = (200, content_type, html.encode("utf-8"))
        return self.url_for(clean_path)

    def serve_json(self, path: str, data: object) -> str:
        """Регистрирует маршрут, отдающий JSON данные.

        Args:
            path: Путь URL.
            data: Данные для сериализации в JSON.

        Returns:
            Абсолютный URL зарегистрированного маршрута.
        """
        clean_path = path if path.startswith("/") else f"/{path}"
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self._routes[clean_path] = (200, "application/json; charset=utf-8", payload)
        return self.url_for(clean_path)

    def fetch(
        self,
        path_or_url: str,
        method: str = "GET",
        headers: Mapping[str, str] | None = None,
        data: bytes | None = None,
    ) -> TestResponse:
        """Выполняет прямой HTTP-запрос к серверу в обход системных прокси.

        Args:
            path_or_url: Путь маршрута (например, '/page') или полный URL.
            method: Метод HTTP (GET, POST и т.д.).
            headers: Опциональные HTTP-заголовки.
            data: Опциональное тело запроса в байтах.

        Returns:
            Экземпляр TestResponse с кодом, заголовками и телом ответа.
        """
        if not self.is_running:
            self.start()

        target_url = (
            path_or_url
            if path_or_url.startswith(("http://", "https://"))
            else self.url_for(path_or_url)
        )

        req_headers = dict(headers) if headers else {}
        req = urllib.request.Request(
            url=target_url,
            data=data,
            headers=req_headers,
            method=method,
        )

        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            with opener.open(req) as resp:
                status = resp.status
                resp_headers = {k: v for k, v in resp.headers.items()}
                content = resp.read()
                return TestResponse(
                    status=status, headers=resp_headers, content=content
                )
        except urllib.error.HTTPError as err:
            err_headers = {k: v for k, v in err.headers.items()} if err.headers else {}
            err_content = err.read()
            return TestResponse(
                status=err.code, headers=err_headers, content=err_content
            )

    def start(self) -> Self:
        """Запускает HTTP-сервер в фоновом потоке.

        Returns:
            Экземпляр сервера.
        """
        if self.is_running:
            return self

        self._httpd = _CustomHTTPServer(
            (self.host, self._requested_port),
            _TestHandler,
            owner=self,
        )
        self._actual_port = self._httpd.server_address[1]

        self._thread = threading.Thread(
            target=self._httpd.serve_forever,
            daemon=True,
            name=f"LocalTestServer-{self.port}",
        )
        self._thread.start()
        logger.debug("Запущен LocalTestServer на %s:%d", self.host, self.port)
        return self

    def stop(self) -> None:
        """Останавливает сервер и фоновый поток."""
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None

        if self._thread is not None:
            self._thread.join(timeout=3.0)
            self._thread = None

        logger.debug("Остановлен LocalTestServer на порту %d", self._actual_port)

    def __enter__(self) -> Self:
        """Вход в синхронный контекстный менеджер."""
        return self.start()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Выход из синхронного контекстного менеджера."""
        self.stop()

    async def __aenter__(self) -> Self:
        """Вход в асинхронный контекстный менеджер."""
        return self.start()

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Выход из асинхронного контекстного менеджера."""
        self.stop()
