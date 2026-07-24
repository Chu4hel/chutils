"""
Тесты для SSE-клиента конфигурации (SseConfigClient) и SSE-парсера.
"""

from __future__ import annotations

import io
import time
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from chutils.config.sse import SseConfigClient, SseEvent, parse_sse_lines

if TYPE_CHECKING:
    pass


class TestSseParser:
    """Тесты для функции парсинга SSE-потока."""

    def test_parse_simple_data_event(self) -> None:
        """Проверка парсинга простого SSE события со строкой data."""
        lines = ["data: hello world\n", "\n"]
        events = list(parse_sse_lines(lines))
        assert len(events) == 1
        assert events[0].event == "message"
        assert events[0].data == "hello world"

    def test_parse_custom_event_type_and_id(self) -> None:
        """Проверка парсинга события с указанием event и id."""
        lines = [
            "event: reload\n",
            "id: 42\n",
            "data: {\"config_version\": 2}\n",
            "\n",
        ]
        events = list(parse_sse_lines(lines))
        assert len(events) == 1
        assert events[0].event == "reload"
        assert events[0].data == '{"config_version": 2}'
        assert events[0].event_id == "42"

    def test_parse_multiline_data_and_retry(self) -> None:
        """Проверка многострочных данных и поля retry."""
        lines = [
            ": this is a comment\n",
            "retry: 5000\n",
            "data: line1\n",
            "data: line2\n",
            "\n",
        ]
        events = list(parse_sse_lines(lines))
        assert len(events) == 1
        assert events[0].data == "line1\nline2"
        assert events[0].retry == 5000

    def test_ignore_comments_and_empty_events(self) -> None:
        """Проверка игнорирования комментариев и пустых строк без данных."""
        lines = [
            ": comment 1\n",
            "\n",
            ": comment 2\n",
            "\n",
        ]
        events = list(parse_sse_lines(lines))
        assert len(events) == 0


class TestSseConfigClient:
    """Тесты для класса SseConfigClient."""

    def test_client_init_defaults(self) -> None:
        """Проверка инициализации клиента по умолчанию."""
        client = SseConfigClient(url="http://example.com/sse")
        assert client.url == "http://example.com/sse"
        assert not client.is_running

    def test_client_custom_headers(self) -> None:
        """Проверка передачи пользовательских заголовков."""
        headers = {"Authorization": "Bearer secret_token", "X-Custom": "val"}
        client = SseConfigClient(url="http://example.com/sse", headers=headers)
        req = client._create_request()
        assert req.get_header("Authorization") == "Bearer secret_token"
        assert req.get_header("X-custom") == "val"
        assert req.get_header("Accept") == "text/event-stream"

    def test_client_start_stop(self) -> None:
        """Проверка запуска и остановки фонового потока SSE."""
        mock_response = MagicMock()
        mock_response.readline.side_effect = [
            b"event: reload\n",
            b"data: updated\n",
            b"\n",
            b"",  # Конец файла / разрыв
        ]
        mock_response.__enter__.return_value = mock_response

        on_reload_mock = MagicMock()
        on_event_mock = MagicMock()

        client = SseConfigClient(
            url="http://example.com/sse",
            on_event=on_event_mock,
            on_reload=on_reload_mock,
            reconnect_delay=0.01,
        )

        with patch("urllib.request.urlopen", return_value=mock_response):
            client.start()
            assert client.is_running
            # Ждем обработки
            time.sleep(0.1)
            client.stop()
            assert not client.is_running

        on_reload_mock.assert_called()
        on_event_mock.assert_called()
        assert on_event_mock.call_args[0][0].data == "updated"

    def test_reconnect_on_error(self) -> None:
        """Проверка повторного подключения при возникновении ошибки сети."""
        attempt_count = 0

        def fake_urlopen(req: object, timeout: float = 30.0) -> MagicMock:
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count == 1:
                raise OSError("Network error")
            
            mock_res = MagicMock()
            mock_res.readline.side_effect = [
                b"data: ok\n",
                b"\n",
                b"",
            ]
            mock_res.__enter__.return_value = mock_res
            return mock_res

        on_reload_mock = MagicMock()
        client = SseConfigClient(
            url="http://example.com/sse",
            on_reload=on_reload_mock,
            reconnect_delay=0.01,
            max_reconnect_delay=0.05,
        )

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            client.start()
            time.sleep(0.15)
            client.stop()

        assert attempt_count >= 2
        on_reload_mock.assert_called()
