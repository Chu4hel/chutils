"""
Тесты для интеграций с веб-фреймворками (FastAPI, Flask) и управление Webhook в ConfigManager.
"""

from __future__ import annotations

import hmac
import hashlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from chutils.config.integrations import (
    create_fastapi_webhook_route,
    create_flask_webhook_route,
)
from chutils.config.manager import _cm
from chutils.exceptions import OptionalDependencyError


class TestFrameworkIntegrations:
    """Тесты интеграционных хэндлеров для FastAPI и Flask."""

    def test_fastapi_missing_dependency(self) -> None:
        """Бросает OptionalDependencyError, если fastapi не установлен."""
        with patch.dict("sys.modules", {"fastapi": None}):
            with pytest.raises(OptionalDependencyError):
                create_fastapi_webhook_route()

    def test_flask_missing_dependency(self) -> None:
        """Бросает OptionalDependencyError, если flask не установлен."""
        with patch.dict("sys.modules", {"flask": None}):
            with pytest.raises(OptionalDependencyError):
                create_flask_webhook_route()

    @pytest.mark.asyncio
    async def test_fastapi_webhook_success(self) -> None:
        """Проверка успешной валидации и перезагрузки в FastAPI хэндлере."""
        mock_fastapi = MagicMock()
        mock_request = AsyncMock()
        mock_request.body.return_value = b'{"push": true}'
        mock_request.headers = {"X-Chutils-Webhook-Token": "secret"}

        on_reload = MagicMock()

        with patch.dict("sys.modules", {"fastapi": mock_fastapi}):
            handler = create_fastapi_webhook_route(
                secret_token="secret",
                on_reload=on_reload,
            )
            response = await handler(mock_request)
            on_reload.assert_called_once()

    def test_flask_webhook_success(self) -> None:
        """Проверка успешной работы Flask хэндлера."""
        mock_flask = MagicMock()
        mock_request = MagicMock()
        mock_request.get_data.return_value = b'{"push": true}'
        mock_request.headers = {"Authorization": "Bearer secret"}

        mock_flask.request = mock_request
        mock_flask.jsonify.side_effect = lambda data: data

        on_reload = MagicMock()

        with patch.dict("sys.modules", {"flask": mock_flask}):
            with patch("chutils.config.integrations.request", mock_request, create=True):
                handler = create_flask_webhook_route(
                    secret_token="secret",
                    on_reload=on_reload,
                )
                res_data, code = handler()
                assert code == 200
                assert res_data == {"status": "reloaded"}
                on_reload.assert_called_once()


class TestConfigManagerWebhook:
    """Тесты управления жизненным циклом Webhook-сервера в ConfigManager."""

    def setup_method(self) -> None:
        _cm._reset()

    def teardown_method(self) -> None:
        _cm._reset()

    def test_start_stop_webhook_server(self) -> None:
        """Проверка запуска и остановки встроенного Webhook-сервера через _cm."""
        server = _cm.start_webhook_server(port=0, path="/reload", secret_token="tok")
        assert server is not None
        assert _cm.webhook_server is not None
        assert _cm.webhook_server.is_running

        _cm.stop_webhook_server()
        assert _cm.webhook_server is None
