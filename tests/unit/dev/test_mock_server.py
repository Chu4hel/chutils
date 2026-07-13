from __future__ import annotations

import json
import os
import shutil
import socket
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Generator

import pytest

from chutils.dev.mock_server import MockServerRunner, interpolate_groups
from chutils.exceptions import CommandError

# Отключаем системный прокси для urllib в тестах, чтобы локальные запросы шли напрямую
urllib.request.install_opener(urllib.request.build_opener(urllib.request.ProxyHandler({})))


def get_free_port() -> int:
    """Возвращает свободный порт в операционной системе."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return int(s.getsockname()[1])


def test_interpolate_groups() -> None:
    # Строковые значения
    assert interpolate_groups("User $1 details", ("42",)) == "User 42 details"
    assert interpolate_groups("Group $1 and $2", ("A", "B")) == "Group A and B"

    # Словари
    data_dict: dict[str, object] = {
        "id": "$1",
        "nested": {
            "name": "User $1",
            "age": 25,  # Должно остаться числом
        }
    }
    expected_dict = {
        "id": "100",
        "nested": {
            "name": "User 100",
            "age": 25,
        }
    }
    assert interpolate_groups(data_dict, ("100",)) == expected_dict

    # Списки
    data_list: list[object] = ["$1", {"value": "$2"}, 42]
    expected_list = ["apple", {"value": "orange"}, 42]
    assert interpolate_groups(data_list, ("apple", "orange")) == expected_list


def test_mock_server_init_template() -> None:
    temp_dir = tempfile.mkdtemp()
    try:
        output_file = Path(temp_dir) / "mocks.yml"
        runner = MockServerRunner(routes_path=str(output_file))

        runner.init_template(str(output_file))
        assert output_file.is_file()
        content = output_file.read_text(encoding="utf-8")
        assert "path: /api/users" in content
        assert "delay: 2.5" in content

        # Повторная инициализация поверх существующего файла должна вызывать ошибку
        with pytest.raises(CommandError, match="уже существует"):
            runner.init_template(str(output_file))
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_mock_server_load_config_errors() -> None:
    temp_dir = tempfile.mkdtemp()
    try:
        # Файл не найден
        runner = MockServerRunner(routes_path="non_existent_file.yml")
        with pytest.raises(CommandError, match="не найден"):
            runner.load_config()

        # Невалидный YAML/JSON
        bad_file = Path(temp_dir) / "bad_mocks.yml"
        bad_file.write_text("invalid: - [ : yaml", encoding="utf-8")
        runner_bad = MockServerRunner(routes_path=str(bad_file))
        with pytest.raises(CommandError, match="Не удалось распарсить"):
            runner_bad.load_config()

        # Конфигурация не является списком
        dict_file = Path(temp_dir) / "dict_mocks.yml"
        dict_file.write_text("path: /api/users\nresponse: ok", encoding="utf-8")
        runner_dict = MockServerRunner(routes_path=str(dict_file))
        with pytest.raises(CommandError, match="должна быть списком"):
            runner_dict.load_config()
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def mock_server() -> Generator[tuple[MockServerRunner, int, Path, str], None, None]:
    """Фикстура для запуска тестового инстанса мок-сервера в реальной файловой системе."""
    temp_dir = tempfile.mkdtemp()
    routes_file = Path(temp_dir) / "mocks.yml"
    initial_config = """
- path: /api/hello
  method: GET
  status: 200
  response:
    message: "hello world"

- path: /api/users/(\\d+)
  method: GET
  is_regex: true
  status: 200
  response:
    id: "$1"
    status: "mocked"

- path: /api/slow
  method: GET
  delay: 0.2
  status: 200
  response: "slow"
"""
    routes_file.write_text(initial_config, encoding="utf-8")

    port = get_free_port()
    runner = MockServerRunner(port=port, routes_path=str(routes_file))
    runner.load_config()

    # Запускаем в отдельном потоке
    server_thread = threading.Thread(target=runner.run)
    server_thread.daemon = True
    server_thread.start()

    # Даем серверу время стартовать
    time.sleep(0.15)

    yield runner, port, routes_file, temp_dir

    # Очистка ресурсов после теста
    runner.stop()
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_server_mock_requests(mock_server: tuple[MockServerRunner, int, Path, str]) -> None:
    runner, port, _, _ = mock_server

    try:
        # Тест простого GET запроса
        url = f"http://127.0.0.1:{port}/api/hello"
        with urllib.request.urlopen(url) as response:
            assert response.status == 200
            data = json.loads(response.read().decode("utf-8"))
            assert data == {"message": "hello world"}

        # Тест regex сопоставления с подстановкой групп
        url_regex = f"http://127.0.0.1:{port}/api/users/999"
        with urllib.request.urlopen(url_regex) as response:
            assert response.status == 200
            data = json.loads(response.read().decode("utf-8"))
            assert data == {"id": "999", "status": "mocked"}

        # Тест 404
        url_404 = f"http://127.0.0.1:{port}/api/non-existent"
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(url_404)
        assert exc_info.value.code == 404
    except Exception:
        print("\n--- DEBUG LOG FROM RUNNER ---\n" + "\n".join(runner.debug_log))
        raise


def test_server_delay(mock_server: tuple[MockServerRunner, int, Path, str]) -> None:
    _, port, _, _ = mock_server
    url = f"http://127.0.0.1:{port}/api/slow"

    start_time = time.time()
    with urllib.request.urlopen(url) as response:
        assert response.status == 200
    duration = time.time() - start_time
    assert duration >= 0.2


def test_server_hot_reload(mock_server: tuple[MockServerRunner, int, Path, str]) -> None:
    _, port, routes_file, _ = mock_server

    # Перезаписываем файл конфигурации роутов
    new_config = """
- path: /api/hello
  method: GET
  status: 201
  response:
    message: "updated hello"
"""
    routes_file.write_text(new_config, encoding="utf-8")

    # Принудительно устанавливаем mtime файла на 2 секунды вперед, чтобы Hot-Reload точно сработал
    future_time = time.time() + 2.0
    os.utime(routes_file, (future_time, future_time))

    # Делаем запрос - сервер должен автоматически перечитать конфиг
    url = f"http://127.0.0.1:{port}/api/hello"
    with urllib.request.urlopen(url) as response:
        assert response.status == 201
        data = json.loads(response.read().decode("utf-8"))
        assert data == {"message": "updated hello"}


def test_server_proxy_fallback() -> None:
    temp_dir = tempfile.mkdtemp()
    try:
        # 1. Запускаем "реальный" целевой бэкенд на свободном порту
        backend_port = get_free_port()
        backend_routes_file = Path(temp_dir) / "backend_mocks.yml"
        backend_config = """
- path: /api/real-data
  method: GET
  status: 200
  response:
    source: "real backend"

- path: /api/submit
  method: POST
  status: 201
  response:
    result: "accepted"
"""
        backend_routes_file.write_text(backend_config, encoding="utf-8")
        backend_runner = MockServerRunner(port=backend_port, routes_path=str(backend_routes_file))
        backend_runner.load_config()

        backend_thread = threading.Thread(target=backend_runner.run)
        backend_thread.daemon = True
        backend_thread.start()

        # 2. Запускаем наш мок-сервер с включенным --proxy-fallback
        proxy_port = get_free_port()
        proxy_routes_file = Path(temp_dir) / "proxy_mocks.yml"
        proxy_config = """
- path: /api/local-mock
  method: GET
  status: 200
  response:
    source: "local mock"
"""
        proxy_routes_file.write_text(proxy_config, encoding="utf-8")
        proxy_runner = MockServerRunner(
            port=proxy_port,
            routes_path=str(proxy_routes_file),
            proxy_fallback=f"http://127.0.0.1:{backend_port}"
        )
        proxy_runner.load_config()

        proxy_thread = threading.Thread(target=proxy_runner.run)
        proxy_thread.daemon = True
        proxy_thread.start()

        time.sleep(0.15)

        # 3. Делаем запросы на прокси-сервер

        # а) Запрос, который переопределен локально (должен вернуть мок)
        url_local = f"http://127.0.0.1:{proxy_port}/api/local-mock"
        with urllib.request.urlopen(url_local) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert data == {"source": "local mock"}

        # б) Запрос, которого нет локально (должен уйти на реальный бэкенд через прокси)
        url_proxy = f"http://127.0.0.1:{proxy_port}/api/real-data"
        with urllib.request.urlopen(url_proxy) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert data == {"source": "real backend"}

        # в) POST запрос с телом данных через прокси
        url_post = f"http://127.0.0.1:{proxy_port}/api/submit"
        req = urllib.request.Request(
            url_post,
            data=json.dumps({"test": "value"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 201
            data = json.loads(resp.read().decode("utf-8"))
            assert data == {"result": "accepted"}
    finally:
        if 'backend_runner' in locals():
            backend_runner.stop()
        if 'proxy_runner' in locals():
            proxy_runner.stop()
        shutil.rmtree(temp_dir, ignore_errors=True)
