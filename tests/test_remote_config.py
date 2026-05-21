import time
import unittest
import urllib.error
from unittest.mock import patch, MagicMock

from chutils.config.core import get_config
from chutils.config.manager import _cm
from chutils.config.providers import HttpConfigProvider


class TestRemoteConfig(unittest.TestCase):

    def setUp(self):
        _cm._reset()

    def tearDown(self):
        if _cm.remote_provider:
            _cm.remote_provider.stop_polling()
        _cm._reset()

    @patch('urllib.request.urlopen')
    def test_http_provider_load_yaml(self, mock_urlopen):
        # Mock successful YAML response
        mock_response = MagicMock()
        mock_response.read.return_value = b"Section:\n  key: value"
        mock_response.headers = {"Content-Type": "application/x-yaml"}
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        provider = HttpConfigProvider(url="http://example.com/config.yml")
        data = provider.load()

        self.assertEqual(data, {"Section": {"key": "value"}})
        mock_urlopen.assert_called_once()

    @patch('urllib.request.urlopen')
    def test_http_provider_load_json(self, mock_urlopen):
        # Mock successful JSON response
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"Section": {"key": "value"}}'
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        provider = HttpConfigProvider(url="http://example.com/config.json")
        data = provider.load()

        self.assertEqual(data, {"Section": {"key": "value"}})

    @patch('urllib.request.urlopen')
    def test_http_provider_auth(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = b"{}"
        mock_response.headers = {}
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        provider = HttpConfigProvider(url="http://example.com/config.yml", username="user", password="password")
        provider.load()

        args, _ = mock_urlopen.call_args
        req = args[0]
        self.assertEqual(req.get_header("Authorization"), "Basic dXNlcjpwYXNzd29yZA==")

    @patch('urllib.request.urlopen')
    def test_http_provider_error_fallback(self, mock_urlopen):
        # 1. Success first to populate cache
        mock_response = MagicMock()
        mock_response.read.return_value = b"key: value"
        mock_response.headers = {}
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        provider = HttpConfigProvider(url="http://example.com/config.yml")
        provider.load()
        self.assertEqual(provider._cache, {"key": "value"})

        # 2. Failure second to test fallback
        mock_urlopen.side_effect = urllib.error.HTTPError("url", 500, "Internal Server Error", {}, None)

        data = provider.load()
        self.assertEqual(data, {"key": "value"})  # Returned from cache

    @patch('urllib.request.urlopen')
    def test_get_config_integration(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = b"Remote:\n  enabled: true"
        mock_response.headers = {}
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        # We need some local config to merge with
        with patch('chutils.config.core._cm.get_config_paths') as mock_paths:
            mock_paths.return_value = (None, None, None)

            config = get_config(remote_url="http://example.com/remote.yml")

            self.assertTrue(config["Remote"]["enabled"])
            self.assertIsNotNone(_cm.remote_provider)

    @patch('urllib.request.urlopen')
    def test_dynamic_polling(self, mock_urlopen):
        # Первый ответ возвращает короткий интервал 0.1 сек
        mock_response1 = MagicMock()
        mock_response1.read.return_value = b"polling:\n  interval: 0.1"
        mock_response1.headers = {}
        mock_response1.__enter__.return_value = mock_response1

        # Второй ответ возвращает данные и меняет интервал на длинный
        mock_response2 = MagicMock()
        mock_response2.read.return_value = b"polling:\n  interval: 60\ndata: updated"
        mock_response2.headers = {}
        mock_response2.__enter__.return_value = mock_response2

        mock_urlopen.side_effect = [mock_response1, mock_response2, mock_response2]

        provider = HttpConfigProvider(url="http://example.com/remote.yml")

        # Запускаем опрос с коротким интервалом
        provider.start_polling(interval=0.2)

        # Ждем немного, чтобы воркер успел выполнить хотя бы два цикла
        time.sleep(1.0)

        self.assertEqual(provider._cache.get("data"), "updated")
        provider.stop_polling()


if __name__ == '__main__':
    unittest.main()
