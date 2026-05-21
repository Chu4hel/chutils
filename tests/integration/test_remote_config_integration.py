"""
Интеграционный тест для HttpConfigProvider.
ПРЕДУПРЕЖДЕНИЕ: Требует наличия интернет-соединения.

Этот тест обращается к реальному онлайн-сервису JSONPlaceholder
для проверки сетевой логики и парсинга без использования моков.
"""

import unittest

from chutils.config.providers import HttpConfigProvider
from chutils.exceptions import ConfigLoadError


class TestRemoteConfigIntegration(unittest.TestCase):

    def test_load_from_real_service(self):
        # Используем стабильный публичный JSON API
        url = "https://jsonplaceholder.typicode.com/todos/1"
        provider = HttpConfigProvider(url=url, timeout=15)

        try:
            data = provider.load()

            print(f"\n[ИНТЕГРАЦИЯ] Данные успешно получены с {url}")
            print(f"[ИНТЕГРАЦИЯ] Содержимое: {data}")

            # Проверяем структуру (JSONPlaceholder возвращает объект с userId, id, title, completed)
            self.assertIn("id", data)
            self.assertIn("title", data)
            self.assertEqual(data["id"], 1)

        except ConfigLoadError as e:
            self.fail(f"Интеграционный тест провалился из-за ошибки сети или таймаута: {e}")
        except Exception as e:
            self.fail(f"Непредвиденная ошибка в интеграционном тесте: {e}")

    def test_error_on_invalid_url(self):
        # Проверяем реакцию на несуществующий домен
        url = "https://non-existent-domain-chutils-test.com/config.json"
        provider = HttpConfigProvider(url=url, timeout=5)

        with self.assertRaises(ConfigLoadError):
            provider.load()


if __name__ == '__main__':
    unittest.main()
