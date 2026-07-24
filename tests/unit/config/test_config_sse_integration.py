"""
Интеграционные тесты для связки ConfigManager и SseConfigClient.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from chutils.config.core import get_config
from chutils.config.manager import _cm
from chutils.config.sse import SseConfigClient
from chutils.config.watcher import on_config_change


class TestSseConfigManagerIntegration:
    """Тесты интеграции SSE-клиента с ConfigManager."""

    def setup_method(self) -> None:
        """Сброс состояния менеджера перед каждым тестом."""
        _cm._reset()

    def teardown_method(self) -> None:
        """Сброс состояния менеджера после каждого теста."""
        _cm._reset()

    def test_trigger_reload_clears_cache_and_notifies_callbacks(self) -> None:
        """Проверка работы trigger_reload в _ConfigManager."""
        callback_mock = MagicMock()
        on_config_change(callback_mock)

        _cm.set_config({"section": {"key": "value"}})
        assert _cm.config_loaded

        _cm.trigger_reload()

        assert not _cm.config_loaded
        callback_mock.assert_called_once()

    def test_get_config_starts_sse_client(self) -> None:
        """Проверка запускa SseConfigClient при вызове get_config с sse_url."""
        mock_response = MagicMock()
        mock_response.readline.side_effect = [
            b": keep-alive\n",
            b"\n",
            b"",
        ]
        mock_response.__enter__.return_value = mock_response

        with patch("urllib.request.urlopen", return_value=mock_response):
            get_config(sse_url="http://example.com/events")
            assert _cm.sse_client is not None
            assert _cm.sse_client.is_running
            assert _cm.sse_client.url == "http://example.com/events"

            # Очистка
            _cm._reset()

    def test_sse_event_triggers_reload_and_callback(self) -> None:
        """Проверка, что получение события SSE вызывает trigger_reload."""
        mock_response = MagicMock()
        mock_response.readline.side_effect = [
            b"event: reload\n",
            b"data: updated\n",
            b"\n",
            b"",
        ]
        mock_response.__enter__.return_value = mock_response

        callback_mock = MagicMock()
        on_config_change(callback_mock)

        with patch("urllib.request.urlopen", return_value=mock_response):
            get_config(sse_url="http://example.com/events")
            time.sleep(0.15)

        callback_mock.assert_called()
