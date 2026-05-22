"""
Пример использования удаленной конфигурации (Remote Configuration).
Демонстрирует загрузку конфига по HTTP, Basic Auth и фоновый опрос (polling).

Для запуска этого примера не требуется внешний сервер, так как мы запустим
временный локальный HTTP-сервер прямо в этом скрипте.
"""

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

from chutils import get_config, setup_logger

logger = setup_logger()


# 1. Создаем простой HTTP сервер для имитации удаленного конфига
class ConfigHandler(BaseHTTPRequestHandler):
    # Счетчик для имитации изменения конфига при опросе
    counter = 0

    def do_GET(self):
        ConfigHandler.counter += 1

        # Проверяем Basic Auth (admin:secret)
        auth_header = self.headers.get('Authorization')
        if auth_header != 'Basic YWRtaW46c2VjcmV0':  # base64(admin:secret)
            self.send_response(401)
            self.send_header('WWW-Authenticate', 'Basic realm="Config"')
            self.end_headers()
            return

        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()

        # Динамически меняем версию в ответе
        config_data = {
            "App": {
                "version": f"1.0.{ConfigHandler.counter}",
                "status": "alive"
            },
            "RemoteConfig": {
                "interval": 2  # Устанавливаем интервал опроса 2 секунды
            }
        }
        self.wfile.write(json.dumps(config_data).encode())

    def log_message(self, format, *args):
        # Отключаем логи сервера в консоль для чистоты примера
        return


def run_mock_server():
    server = HTTPServer(('127.0.0.1', 8888), ConfigHandler)
    server.serve_forever()


# Запускаем сервер в фоновом потоке
threading.Thread(target=run_mock_server, daemon=True).start()
time.sleep(1)  # Даем серверу время запуститься


def main():
    logger.info("--- Шаг 1: Первая загрузка удаленного конфига ---")

    # Загружаем конфиг с удаленного URL
    # Мы указываем remote_auth и polling_interval
    config = get_config(
        remote_url="http://127.0.0.1:8888/config.json",
        remote_auth=("admin", "secret"),
        polling_interval=5  # Начальный интервал (будет переопределен сервером на 2 сек)
    )

    logger.info(f"Загруженная версия: {config.get('App', {}).get('version')}")

    logger.info("\n--- Шаг 2: Ожидание автоматического обновления (Polling) ---")
    logger.info("Мы установили интервал 2 сек в конфиге. Ждем 5 секунд...")

    for i in range(5):
        time.sleep(1)
        # При каждом вызове get_config() мы будем получать актуальные данные из кэша,
        # который обновляется в фоновом потоке.
        current_config = get_config()
        version = current_config.get('App', {}).get('version')
        logger.info(f"Секунда {i + 1}, текущая версия в приложении: {version}")

    logger.info("\n--- Пример завершен ---")


if __name__ == "__main__":
    main()
