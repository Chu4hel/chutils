"""
Тесты для встроенного Webhook-сервера и функции валидации Webhook.
"""

from __future__ import annotations

import hmac
import hashlib
import json
import urllib.request
from unittest.mock import MagicMock

import pytest

from chutils.config.webhook_server import (
    WebhookConfigServer,
    verify_webhook_request,
)


class TestWebhookValidation:
    """Тесты функции валидации запросов verify_webhook_request."""

    def test_no_auth_required(self) -> None:
        """Валидация без токена и HMAC проходит успешно."""
        valid, code, msg = verify_webhook_request({}, b"data")
        assert valid
        assert code == 200

    def test_token_validation_success(self) -> None:
        """Проверка успеха с верным токеном."""
        headers = {"X-Chutils-Webhook-Token": "my_secret"}
        valid, code, _ = verify_webhook_request(headers, b"", secret_token="my_secret")
        assert valid
        assert code == 200

    def test_token_validation_bearer_success(self) -> None:
        """Проверка успеха с Bearer токеном."""
        headers = {"Authorization": "Bearer my_secret"}
        valid, code, _ = verify_webhook_request(headers, b"", secret_token="my_secret")
        assert valid
        assert code == 200

    def test_token_validation_missing_and_invalid(self) -> None:
        """Проверка ошибок при отсутствии или неверном токене."""
        valid, code, _ = verify_webhook_request({}, b"", secret_token="my_secret")
        assert not valid
        assert code == 401

        headers = {"X-Chutils-Webhook-Token": "wrong"}
        valid, code, _ = verify_webhook_request(headers, b"", secret_token="my_secret")
        assert not valid
        assert code == 403

    def test_hmac_validation_success(self) -> None:
        """Проверка верной HMAC-SHA256 подписи."""
        body = b'{"event": "push"}'
        secret = "super_key"
        sig = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()

        headers = {"X-Chutils-Signature": sig}
        valid, code, _ = verify_webhook_request(headers, body, hmac_secret=secret)
        assert valid
        assert code == 200

        # Также с префиксом sha256=
        headers_prefix = {"X-Hub-Signature-256": f"sha256={sig}"}
        valid, code, _ = verify_webhook_request(headers_prefix, body, hmac_secret=secret)
        assert valid

    def test_hmac_validation_invalid(self) -> None:
        """Проверка ошибки неверной HMAC подписи."""
        body = b'{"event": "push"}'
        headers = {"X-Chutils-Signature": "wrong_sig"}
        valid, code, _ = verify_webhook_request(headers, body, hmac_secret="super_key")
        assert not valid
        assert code == 403


class TestWebhookConfigServer:
    """Тесты работы встроенного Webhook HTTP-сервера."""

    def test_server_lifecycle_and_post_reload(self) -> None:
        """Запуск сервера на порт 0 (случайный порт), отправка POST запроса и вызов reload."""
        on_reload_mock = MagicMock()
        server = WebhookConfigServer(
            host="127.0.0.1",
            port=0,
            path="/reload",
            secret_token="token123",
            on_reload=on_reload_mock,
        )
        server.start()
        actual_port = server.port
        assert actual_port > 0

        try:
            url = f"http://127.0.0.1:{actual_port}/reload"
            req = urllib.request.Request(
                url,
                data=b'{"action": "reload"}',
                headers={"X-Chutils-Webhook-Token": "token123"},
                method="POST",
            )

            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(req) as resp:
                assert resp.status == 200
                res_body = json.loads(resp.read().decode("utf-8"))
                assert res_body["status"] == "reloaded"

            on_reload_mock.assert_called_once()
        finally:
            server.stop()

    def test_server_unauthorized_post(self) -> None:
        """Сервер отклоняет запрос без токена с 401."""
        server = WebhookConfigServer(
            host="127.0.0.1",
            port=0,
            path="/reload",
            secret_token="token123",
        )
        server.start()
        actual_port = server.port

        try:
            url = f"http://127.0.0.1:{actual_port}/reload"
            req = urllib.request.Request(url, data=b"{}", method="POST")

            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with pytest.raises(urllib.error.HTTPError) as exc_info:
                opener.open(req)

            assert exc_info.value.code == 401
        finally:
            server.stop()
