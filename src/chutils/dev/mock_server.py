from __future__ import annotations

import json
import re
import socketserver
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import TypedDict, Union, cast

from chutils.exceptions import CommandError

# Попытка импортировать pyyaml для поддержки YAML
try:
    import yaml

    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


class RouteConfig(TypedDict, total=False):
    """Конфигурация отдельного маршрута мок-сервера."""
    path: str
    method: str
    response: Union[str, dict[str, object], list[object]]
    status: int
    delay: float
    is_regex: bool


DEFAULT_TEMPLATE = """# Декларативная конфигурация роутов для мок-сервера
# Поддерживаемые методы: GET, POST, PUT, DELETE, PATCH
# Поддерживается задержка (delay в секундах) и кастомные статусы (status)

- path: /api/users
  method: GET
  status: 200
  response:
    users:
      - id: 1
        name: Иван Иванов
        email: ivan@example.com
      - id: 2
        name: Петр Петров
        email: petr@example.com

- path: /api/users/(\\d+)
  method: GET
  is_regex: true
  status: 200
  response:
    id: "$1"
    name: "Пользователь $1"
    email: "user$1@example.com"
    status: "mocked"

- path: /api/users
  method: POST
  status: 201
  response:
    success: true
    message: "Пользователь успешно создан"

- path: /api/slow-endpoint
  method: GET
  delay: 2.5
  status: 200
  response:
    message: "Этот ответ пришел с задержкой 2.5 секунды"

- path: /api/error
  method: GET
  status: 500
  response:
    error: "Internal Server Error"
    code: 50001
    message: "Имитация внутренней ошибки сервера"
"""


def interpolate_groups(
        val: Union[str, dict[str, object], list[object]],
        groups: tuple[str, ...],
) -> Union[str, dict[str, object], list[object]]:
    """Рекурсивно подставляет значения групп регулярного выражения вместо $1, $2 и т.д.

    Args:
        val: Значение для интерполяции (строка, словарь или список).
        groups: Кортеж найденных групп из регулярного выражения.

    Returns:
        Интерполированное значение того же типа.
    """
    if isinstance(val, str):
        result = val
        for i, group_val in enumerate(groups, 1):
            result = result.replace(f"${i}", group_val)
        return result
    elif isinstance(val, dict):
        new_dict: dict[str, object] = {}
        for k, v in val.items():
            if isinstance(v, (str, dict, list)):
                new_dict[k] = interpolate_groups(v, groups)
            else:
                new_dict[k] = v
        return new_dict
    elif isinstance(val, list):
        new_list: list[object] = []
        for item in val:
            if isinstance(item, (str, dict, list)):
                new_list.append(interpolate_groups(item, groups))
            else:
                new_list.append(item)
        return new_list
    return val


class MockHTTPRequestHandler(BaseHTTPRequestHandler):
    """Обработчик HTTP-запросов для мок-сервера."""

    @property
    def runner(self) -> MockServerRunner:
        """Получает инстанс MockServerRunner, привязанный к серверу.

        Returns:
            Экземпляр MockServerRunner.
        """
        return cast(MockServerRunner, getattr(self.server, "runner"))

    # Переопределяем логирование по умолчанию, чтобы не мусорить в stdout
    def log_message(self, format: str, *args: object) -> None:
        """Переопределяет логирование по умолчанию, чтобы не мусорить в stdout."""
        pass

    def handle_request(self) -> None:
        """Общая логика обработки входящего запроса."""
        try:
            method = self.command.upper()
            path_without_query = self.path.split("?")[0]
            self.runner.debug_log.append(f"Request: {method} {path_without_query}")

            # Hot-Reload: проверяем изменения в файле конфигурации
            self.runner.check_reload()

            # Ищем подходящий роут
            matched_route: RouteConfig | None = None
            matched_groups: tuple[str, ...] = ()

            for route in self.runner.routes:
                route_method = route.get("method", "GET").upper()
                if route_method != method:
                    continue

                route_path = route.get("path", "")
                is_regex = route.get("is_regex", False)

                if is_regex:
                    try:
                        pattern = re.compile(f"^{route_path}$")
                        match = pattern.match(path_without_query)
                        if match:
                            matched_route = route
                            matched_groups = match.groups()
                            break
                    except re.error:
                        continue
                else:
                    if route_path == path_without_query:
                        matched_route = route
                        break

            self.runner.debug_log.append(f"Matched route: {matched_route}")

            if matched_route:
                # 1. Симуляция задержки
                delay = float(matched_route.get("delay", 0.0))
                if delay > 0:
                    time.sleep(delay)

                # 2. Подготовка статус-кода
                status = int(matched_route.get("status", 200))

                # 3. Подготовка и интерполяция ответа
                raw_response = matched_route.get("response", "")
                interpolated = interpolate_groups(raw_response, matched_groups)

                if isinstance(interpolated, (dict, list)):
                    response_bytes = json.dumps(
                        interpolated, ensure_ascii=False
                    ).encode("utf-8")
                else:
                    response_bytes = str(interpolated).encode("utf-8")

                # 4. Отправка ответа с Content-Length
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(response_bytes)))
                self.end_headers()

                self.runner.debug_log.append(f"Writing response_bytes len={len(response_bytes)}")
                self.wfile.write(response_bytes)
                self.wfile.flush()

                # Логирование
                self.runner.log_event(
                    f"[bold green]Mock[/bold green] | {method} {self.path} -> Status {status} | Delay: {delay}s"
                )
            else:
                if self.runner.proxy_fallback:
                    self.runner.debug_log.append("Proxying request")
                    self.proxy_request(method)
                else:
                    self.runner.debug_log.append("Returning 404")
                    err_resp = {
                        "error": "Not Found",
                        "message": f"Роут {method} {self.path} не найден в конфигурации моков.",
                    }
                    response_bytes = json.dumps(err_resp).encode("utf-8")

                    self.send_response(404)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(response_bytes)))
                    self.end_headers()

                    self.wfile.write(response_bytes)
                    self.wfile.flush()
                    self.runner.log_event(
                        f"[bold red]404[/bold red]  | {method} {self.path} -> Не найдено"
                    )
        except Exception as e:
            self.runner.debug_log.append(f"Exception caught: {e}")
            err_resp = {"error": "Internal Error", "details": str(e)}
            response_bytes = json.dumps(err_resp).encode("utf-8")

            try:
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(response_bytes)))
                self.end_headers()
                self.wfile.write(response_bytes)
                self.wfile.flush()
            except Exception:
                pass

    def proxy_request(self, method: str) -> None:
        """Перенаправляет запрос на реальный бэкенд.

        Args:
            method: HTTP-метод запроса (например, GET, POST).
        """
        fallback = self.runner.proxy_fallback
        if not fallback:
            return
        proxy_url = f"{fallback.rstrip('/')}{self.path}"

        # Чтение тела запроса
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else None

        # Фильтруем заголовки (исключаем Host, чтобы не конфликтовать с проксируемым сервером)
        headers: dict[str, str] = {}
        for k, v in self.headers.items():
            if k.lower() != "host":
                headers[k] = v

        req = urllib.request.Request(
            proxy_url,
            data=body,
            headers=headers,
            method=method,
        )

        try:
            with urllib.request.urlopen(req) as resp:
                status = resp.status
                self.send_response(status)

                # Копируем заголовки ответа
                for k, v in resp.headers.items():
                    if k.lower() not in ("transfer-encoding", "content-length"):
                        self.send_header(k, v)
                self.end_headers()

                response_data = resp.read()
                self.wfile.write(response_data)

                self.runner.log_event(
                    f"[bold cyan]Proxy[/bold cyan] | {method} {self.path} -> {proxy_url} | Status {status}"
                )
        except urllib.error.HTTPError as e:
            # Ошибка от проксируемого бэкенда (4xx/5xx)
            self.send_response(e.code)
            for k, v in e.headers.items():
                if k.lower() not in ("transfer-encoding", "content-length"):
                    self.send_header(k, v)
            self.end_headers()
            self.wfile.write(e.read())

            self.runner.log_event(
                f"[bold yellow]Proxy Error[/bold yellow] | {method} {self.path} -> {proxy_url} | Status {e.code}"
            )
        except Exception as e:
            # Ошибка подключения к прокси
            self.send_response(502)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            err_resp = {
                "error": "Bad Gateway",
                "message": f"Не удалось проксировать запрос к {proxy_url}: {e}",
            }
            self.wfile.write(json.dumps(err_resp).encode("utf-8"))
            self.runner.log_event(
                f"[bold red]Proxy Fail[/bold red] | {method} {self.path} -> {proxy_url} | Connection Failed: {e}"
            )

    # Заглушки для HTTP-методов
    def do_GET(self) -> None:
        """Обрабатывает входящий GET-запрос."""
        self.handle_request()

    def do_POST(self) -> None:
        """Обрабатывает входящий POST-запрос."""
        self.handle_request()

    def do_PUT(self) -> None:
        """Обрабатывает входящий PUT-запрос."""
        self.handle_request()

    def do_DELETE(self) -> None:
        """Обрабатывает входящий DELETE-запрос."""
        self.handle_request()

    def do_PATCH(self) -> None:
        """Обрабатывает входящий PATCH-запрос."""
        self.handle_request()


class ThreadingHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    """Многопоточный HTTP сервер."""
    daemon_threads = True


class MockServerRunner:
    """Управляющий класс для мок-сервера."""

    def __init__(
            self,
            port: int = 8888,
            routes_path: str = "mocks.yml",
            proxy_fallback: str | None = None,
    ) -> None:
        """Инициализирует MockServerRunner.

        Args:
            port: Порт, на котором будет запущен мок-сервер.
            routes_path: Путь к YAML-файлу с описанием роутов.
            proxy_fallback: URL реального бэкенда для проксирования неизвестных роутов.
        """
        self.port = port
        self.routes_path = routes_path
        self.proxy_fallback = proxy_fallback
        self.routes: list[RouteConfig] = []
        self._last_loaded: float = 0.0
        self.debug_log: list[str] = []
        self._server: ThreadingHTTPServer | None = None

        # Ленивая инициализация консоли и логгера
        from chutils.cli_utils import get_console
        self.console = get_console()
        # Инициализируем отрисовщик в основном потоке, чтобы избежать KeyError: 'rich._windows_renderer' в фоновых потоках на Windows
        self.console.print("", end="")

    def init_template(self, output_path: str) -> None:
        """Создает шаблонный файл конфигурации роутов.

        Args:
            output_path: Путь к файлу для сохранения шаблона.
        """
        path = Path(output_path).resolve()
        if path.exists():
            raise CommandError(
                f"Файл конфигурации '{output_path}' уже существует. "
                "Удалите его или выберите другой путь."
            )
        path.write_text(DEFAULT_TEMPLATE, encoding="utf-8")
        self.console.print(
            f"[bold green] [OK] [/bold green] Шаблон конфигурации успешно сохранен в: [cyan]{output_path}[/cyan]"
        )

    def log_event(self, message: str) -> None:
        """Выводит отформатированное лог-сообщение в консоль.

        Args:
            message: Текст лог-сообщения.
        """
        from datetime import datetime
        time_str = datetime.now().strftime("%H:%M:%S")
        self.console.print(f"[dim][{time_str}][/dim] {message}")

    def load_config(self) -> None:
        """Загружает роуты из файла (YAML или JSON)."""
        path = Path(self.routes_path).resolve()
        if not path.exists():
            raise CommandError(
                f"Файл роутов '{self.routes_path}' не найден. "
                "Запустите 'chutils dev mock init' для создания шаблона."
            )

        try:
            content = path.read_text(encoding="utf-8")
            if path.suffix in (".yml", ".yaml"):
                if not YAML_AVAILABLE:
                    # Попытка парсинга как JSON, если YAML недоступен
                    try:
                        routes_data = json.loads(content)
                    except json.JSONDecodeError:
                        raise CommandError(
                            "Установленный пакет PyYAML не найден, а файл не является валидным JSON. "
                            "Установите PyYAML ('pip install pyyaml') или используйте JSON конфигурацию."
                        )
                else:
                    routes_data = yaml.safe_load(content)
            else:
                routes_data = json.loads(content)

            if not isinstance(routes_data, list):
                raise CommandError("Конфигурация роутов должна быть списком правил (массивом).")

            validated_routes: list[RouteConfig] = []
            for item in routes_data:
                if not isinstance(item, dict):
                    continue
                route: RouteConfig = {
                    "path": str(item.get("path", "")),
                    "method": str(item.get("method", "GET")).upper(),
                    "response": item.get("response", ""),
                    "status": int(item.get("status", 200)),
                    "delay": float(item.get("delay", 0.0)),
                    "is_regex": bool(item.get("is_regex", False)),
                }
                validated_routes.append(route)

            self.routes = validated_routes
            self._last_loaded = path.stat().st_mtime
        except Exception as e:
            if isinstance(e, CommandError):
                raise
            raise CommandError(f"Не удалось распарсить файл конфигурации '{self.routes_path}': {e}")

    def check_reload(self) -> None:
        """Проверяет время изменения файла на диске и перезагружает при необходимости."""
        path = Path(self.routes_path).resolve()
        if path.exists():
            mtime = path.stat().st_mtime
            if mtime > self._last_loaded:
                try:
                    self.load_config()
                    self.log_event(
                        "[bold magenta]Reload[/bold magenta] | Конфигурация успешно перезагружена с диска."
                    )
                except Exception as e:
                    self.log_event(
                        f"[bold red]Reload Fail[/bold red] | Не удалось перезагрузить файл: {e}"
                    )

    def stop(self) -> None:
        """Останавливает запущенный HTTP-сервер."""
        if hasattr(self, "_server") and self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None

    def run(self) -> None:
        """Запускает многопоточный HTTP-сервер."""
        # Первичная загрузка конфигурации
        self.load_config()

        server_address = ("", self.port)

        # Создаем многопоточный сервер
        server = ThreadingHTTPServer(server_address, MockHTTPRequestHandler)
        # Связываем ссылку на runner с сервером
        server.runner = self  # type: ignore[attr-defined]
        self._server = server

        self.console.print(
            f"[bold green] [OK] [/bold green] Декларативный мок-сервер успешно запущен!\n"
            f"       - [bold]Адрес:[/bold] [cyan]http://localhost:{self.port}[/cyan]\n"
            f"       - [bold]Конфигурация:[/bold] [cyan]{self.routes_path}[/cyan]\n"
            + (
                f"       - [bold]Proxy Fallback:[/bold] [cyan]{self.proxy_fallback}[/cyan]\n" if self.proxy_fallback else "")
            + "       Нажмите [bold red]Ctrl+C[/bold red] для остановки."
        )

        try:
            server.serve_forever()
        except (KeyboardInterrupt, OSError):
            self.console.print("\n[bold yellow]Остановка мок-сервера...[/bold yellow]")
            server.server_close()
