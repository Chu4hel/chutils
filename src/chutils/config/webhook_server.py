"""
Встроенный Webhook-сервер на базе http.server для мгновенного обновления конфигурации.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging  # chutils: ignore[ChutilsIntegrationRule]
import threading
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import ClassVar

logger = logging.getLogger(__name__)


def verify_webhook_request(
    headers: dict[str, str],
    body: bytes,
    secret_token: str | None = None,
    hmac_secret: str | None = None,
) -> tuple[bool, int, str]:
    """
    Валидирует входящий Webhook-запрос по токену и HMAC-подписи.

    Args:
        headers: Словарь HTTP-заголовков.
        body: Сырое тело запроса.
        secret_token: Ожидаемый токен авторизации.
        hmac_secret: Секретный ключ для HMAC-SHA256.

    Returns:
        Кортеж (is_valid, status_code, message).
    """
    headers_lower = {k.lower(): v for k, v in headers.items()}

    if secret_token:
        token_hdr = headers_lower.get("x-chutils-webhook-token") or headers_lower.get("authorization")
        if not token_hdr:
            return False, 401, "Missing authorization token"

        if token_hdr.startswith("Bearer "):
            token_val = token_hdr[7:].strip()
        else:
            token_val = token_hdr.strip()

        if not hmac.compare_digest(token_val, secret_token):
            return False, 403, "Invalid authorization token"

    if hmac_secret:
        sig_hdr = headers_lower.get("x-chutils-signature") or headers_lower.get("x-hub-signature-256")
        if not sig_hdr:
            return False, 401, "Missing HMAC signature header"

        if sig_hdr.startswith("sha256="):
            expected_sig = sig_hdr[7:].strip()
        else:
            expected_sig = sig_hdr.strip()

        computed_sig = hmac.new(
            hmac_secret.encode("utf-8"),
            body,
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(computed_sig, expected_sig):
            return False, 403, "Invalid HMAC signature"

    return True, 200, "OK"


class _WebhookRequestHandler(BaseHTTPRequestHandler):
    """Хэндлер входящих HTTP-запросов для WebhookConfigServer."""

    def log_message(self, format_str: str, *args: object) -> None:
        """
        Подавляем стандартный вывод логирования BaseHTTPRequestHandler.

        Args:
            format_str: Строка формата со спецификаторами printf.
            *args: Аргументы форматирования.
        """
        logger.debug(format_str, *args)

    def do_POST(self) -> None:  # noqa: N802
        """Обрабатывает POST-запросы к эндпоинту Webhook."""
        try:
            app = getattr(self.server, "app_server", None)
            server_path = app.path if app else "/webhook/config-reload"
            secret_token = app.secret_token if app else None
            hmac_secret = app.hmac_secret if app else None
            on_reload = app.on_reload if app else None

            req_path = self.path.split("?")[0]
            if req_path != server_path:
                self._respond(404, {"error": "Not found"})
                return

            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length) if content_length > 0 else b""

            headers_dict = {k: str(v) for k, v in self.headers.items()}
            valid, status_code, message = verify_webhook_request(
                headers=headers_dict,
                body=body,
                secret_token=secret_token,
                hmac_secret=hmac_secret,
            )

            if not valid:
                self._respond(status_code, {"error": message})
                return

            if on_reload:
                try:
                    on_reload()
                except Exception as err:
                    logger.error("Ошибка в обработчике on_reload Webhook: %s", err)
                    self._respond(500, {"error": "Reload failed"})
                    return

            self._respond(200, {"status": "reloaded"})
        except Exception as exc:
            logger.exception("Ошибка в do_POST: %s", exc)
            self._respond(500, {"error": str(exc)})

    def _respond(self, status_code: int, data: dict[str, str]) -> None:
        """Отправляет JSON-ответ клиенту."""
        body_bytes = json.dumps(data).encode("utf-8")
        self.send_response(status_code)
        if status_code == 401:
            self.send_header("WWW-Authenticate", 'Bearer realm="chutils"')
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body_bytes)))
        self.end_headers()
        self.wfile.write(body_bytes)
        self.wfile.flush()


class WebhookConfigServer:
    """
    Легковесный Webhook-сервер для принятия входящих HTTP POST запросов
    и триггера перезагрузки конфигурации.
    """

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8080,
        path: str = "/webhook/config-reload",
        secret_token: str | None = None,
        hmac_secret: str | None = None,
        on_reload: Callable[[], None] | None = None,
    ) -> None:
        """
        Инициализирует WebhookConfigServer.

        Args:
            host: Хост для прослушивания (по умолчанию 0.0.0.0).
            port: Порт для прослушивания (0 — динамический случайный порт).
            path: URL-путь эндпоинта (по умолчанию /webhook/config-reload).
            secret_token: Токен аутентификации.
            hmac_secret: Ключ HMAC-SHA256 подписи.
            on_reload: Колбэк без аргументов для перезагрузки конфига.
        """
        self.host = host
        self.requested_port = port
        self.path = path
        self.secret_token = secret_token
        self.hmac_secret = hmac_secret
        self.on_reload = on_reload

        self._httpd: HTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def is_running(self) -> bool:
        """Возвращает True, если сервер запущен и принимает соединения."""
        return self._httpd is not None and self._thread is not None and self._thread.is_alive()

    @property
    def port(self) -> int:
        """Возвращает фактический номер порта, на котором запущен сервер."""
        if self._httpd and hasattr(self._httpd, "server_address"):
            return int(self._httpd.server_address[1])
        return self.requested_port

    def start(self) -> None:
        """Запускает HTTP-сервер в фоновом потоке."""
        if self.is_running:
            return

        self._httpd = HTTPServer((self.host, self.requested_port), _WebhookRequestHandler)
        setattr(self._httpd, "app_server", self)

        self._thread = threading.Thread(
            target=self._httpd.serve_forever,
            name="WebhookConfigServerThread",
            daemon=True,
        )
        self._thread.start()
        logger.debug("Webhook-сервер запущен на %s:%d%s", self.host, self.port, self.path)

    def stop(self) -> None:
        """Останавливает фоновый HTTP-сервер."""
        if self._httpd:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None

        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

        logger.debug("Webhook-сервер остановлен")
