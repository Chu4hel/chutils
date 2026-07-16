from __future__ import annotations

import argparse
import configparser
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from chutils.env import is_rich_enabled
from .base import BaseCommand

DEFAULT_MIRRORS = [
    "https://pypi.org/simple/",
    "https://mirror.yandex.ru/pypi/simple/",
    "https://mirrors.aliyun.com/pypi/simple/",
    "https://pypi-mirror.gitverse.ru/simple/",
    "https://pypi.depkit.ru/simple/",
    "https://pypi.tuna.tsinghua.edu.cn/simple/",
]


def get_current_index_url() -> str:
    """Возвращает текущий настроенный index-url из pip.

    Returns:
        Текущий настроенный URL индекса пакетов (index-url).
    """
    # 1. Проверяем переменную окружения
    if "PIP_INDEX_URL" in os.environ:  # chutils: ignore[ChutilsIntegrationRule]
        return os.environ["PIP_INDEX_URL"]  # chutils: ignore[ChutilsIntegrationRule]

    # 2. Вызываем pip config через подпроцесс
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "config", "get", "global.index-url"],
            capture_output=True,
            text=True,
            timeout=3
        )
        if result.returncode == 0:
            url = result.stdout.strip()
            if url:
                return url
    except Exception:
        pass

    # 3. Фолбек: парсинг конфигурационных файлов pip
    paths = []
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")  # chutils: ignore[ChutilsIntegrationRule]
        if appdata:
            paths.append(Path(appdata) / "pip" / "pip.ini")
        userprofile = os.environ.get("USERPROFILE")  # chutils: ignore[ChutilsIntegrationRule]
        if userprofile:
            paths.append(Path(userprofile) / "pip" / "pip.ini")
            paths.append(Path(userprofile) / "AppData" / "Roaming" / "pip" / "pip.ini")
    else:
        home = Path.home()
        paths.append(home / ".config" / "pip" / "pip.conf")
        paths.append(home / ".pip" / "pip.conf")

    for path in paths:
        if path.exists():
            try:
                config = configparser.ConfigParser()
                config.read(path)
                if "global" in config and "index-url" in config["global"]:
                    return config["global"]["index-url"]
                if "install" in config and "index-url" in config["install"]:
                    return config["install"]["index-url"]
            except Exception:
                pass

    return "https://pypi.org/simple/"


def normalize_mirror_url(url: str) -> str:
    """Приводит URL зеркала к единому стандарту с закрывающим слэшем.

    Args:
        url: Исходный URL зеркала.

    Returns:
        Нормализованный URL с закрывающим слэшем.
    """
    url = url.strip()
    if not url.endswith("/"):
        url += "/"
    return url


def normalize_url(base_url: str, package: str) -> str:
    """Формирует URL для проверки конкретного пакета.

    Args:
        base_url: Базовый URL зеркала.
        package: Имя пакета.

    Returns:
        Полный URL для запроса индекса пакета на данном зеркале.
    """
    base_url = normalize_mirror_url(base_url)
    return urljoin(base_url, f"{package}/")


def measure_mirror(mirror_url: str, package: str, timeout: float = 3.0) -> dict[str, Any]:
    """Измеряет время отклика и скорость скачивания для конкретного зеркала.

    Args:
        mirror_url: Базовый URL зеркала.
        package: Имя пакета для тестирования.
        timeout: Таймаут для сетевых запросов в секундах.

    Returns:
        Словарь с результатами замеров (доступность, latency, скорость и т.д.).
    """
    result: dict[str, Any] = {
        "url": mirror_url,
        "available": False,
        "latency_ms": None,
        "download_speed_kbs": None,
        "error": None,
        "checked_file_url": None,
    }

    package_url = normalize_url(mirror_url, package)
    headers = {"User-Agent": "pip/23.0"}

    # 1. Замеряем Latency (время отклика)
    start_time = time.perf_counter()
    req = urllib.request.Request(package_url, headers=headers)

    try:
        # Устанавливаем тайм-аут на все операции
        with urllib.request.urlopen(req, timeout=timeout) as response:
            html_bytes = response.read()
            latency = (time.perf_counter() - start_time) * 1000.0
            result["latency_ms"] = latency
            result["available"] = True

            # Парсим HTML для поиска ссылок на файлы пакета
            html = html_bytes.decode("utf-8", errors="ignore")
            hrefs = re.findall(r'<a\s+(?:[^>]*?\s+)?href="([^"]+)"', html)

            file_url = None
            for href in hrefs:
                resolved = urljoin(package_url, href)
                path_part = resolved.split('#')[0]
                if path_part.endswith((".whl", ".tar.gz", ".zip", ".tar.bz2", ".tgz")):
                    file_url = resolved
                    if path_part.endswith(".whl"):
                        break

            if not file_url and hrefs:
                file_url = urljoin(package_url, hrefs[0])

            if file_url:
                result["checked_file_url"] = file_url
                # 2. Замеряем скорость скачивания
                file_req = urllib.request.Request(file_url, headers=headers)
                try:
                    speed_start_time = time.perf_counter()
                    bytes_downloaded = 0
                    max_bytes = 100 * 1024  # Скачиваем не более 100 KB для теста

                    with urllib.request.urlopen(file_req, timeout=timeout) as file_response:
                        while bytes_downloaded < max_bytes:
                            chunk = file_response.read(8192)
                            if not chunk:
                                break
                            bytes_downloaded += len(chunk)

                    duration = time.perf_counter() - speed_start_time
                    if duration > 0 and bytes_downloaded > 0:
                        result["download_speed_kbs"] = (bytes_downloaded / 1024.0) / duration
                    else:
                        result["download_speed_kbs"] = 0.0
                except Exception as e:
                    result["error"] = f"Ошибка скачивания: {type(e).__name__}"
            else:
                result["error"] = "Не найдены ссылки на файлы в индексе"

    except urllib.error.HTTPError as e:
        result["error"] = f"HTTP {e.code}"
    except urllib.error.URLError as e:
        result["error"] = f"Ошибка сети: {e.reason}"
    except TimeoutError:
        result["error"] = "Таймаут"
    except Exception as e:
        result["error"] = f"Ошибка: {str(e)}"

    return result


def find_best_mirror(results: list[dict[str, Any]], current_url: str) -> str | None:
    """Определяет наилучшее зеркало и сравнивает его с текущим.

    Args:
        results: Список результатов замера характеристик зеркал.
        current_url: URL текущего зеркала pip.

    Returns:
        URL наилучшего зеркала, если оно значительно быстрее текущего, иначе None.
    """
    norm_current = normalize_mirror_url(current_url)
    current_result = None
    for r in results:
        if normalize_mirror_url(r["url"]) == norm_current:
            current_result = r
            break

    available_results = [r for r in results if r["available"]]
    if not available_results:
        return None

    # Сортируем: сначала по максимальной скорости скачивания, затем по минимальному latency
    def sort_key(r: dict[str, Any]) -> tuple[float, float]:
        speed = r["download_speed_kbs"] or 0.0
        latency = r["latency_ms"] or float("inf")
        return (-speed, latency)

    best_result = min(available_results, key=sort_key)

    # Если текущее зеркало недоступно или не в списке, рекомендуем лучшее из доступных
    if not current_result or not current_result["available"]:
        return str(best_result["url"])

    # Если лучшее зеркало совпадает с текущим, рекомендация не нужна
    if normalize_mirror_url(best_result["url"]) == norm_current:
        return None

    best_speed = best_result["download_speed_kbs"] or 0.0
    current_speed = current_result["download_speed_kbs"] or 0.0
    best_latency = best_result["latency_ms"] or float("inf")
    current_latency = current_result["latency_ms"] or float("inf")

    # Сравниваем скорость: если скорость выше на 50%+
    if best_speed > 0 and current_speed > 0:
        if best_speed >= current_speed * 1.5:
            return str(best_result["url"])
    elif best_speed > 0 and current_speed == 0:
        return str(best_result["url"])

    # Сравниваем пинг: если пинг ниже на 30%+ и разница не менее 50 мс
    if best_latency < current_latency:
        if current_latency > 0 and best_latency <= current_latency * 0.7 and (current_latency - best_latency) >= 50:
            return str(best_result["url"])

    return None


class PyPiCommand(BaseCommand):
    """
    Проверка доступности и производительности зеркал PyPI.
    
    Позволяет измерять время отклика и скорость загрузки пакетов
    с официального PyPI и различных зеркал.
    """

    def register(self, subparsers: argparse._SubParsersAction[Any]) -> None:
        """Регистрирует команду pypi и её подкоманды в argparse.

        Args:
            subparsers: Объект subparsers для добавления подкоманд.
        """
        check_args_parser = argparse.ArgumentParser(add_help=False)
        check_args_parser.add_argument(
            "-m", "--mirrors",
            help="Кастомные зеркала для проверки (список URL через запятую)"
        )
        check_args_parser.add_argument(
            "--json",
            action="store_true",
            help="Вывод результатов в формате JSON"
        )
        check_args_parser.add_argument(
            "--package",
            default="six",
            help="Имя пакета для теста скорости загрузки (по умолчанию: six)"
        )

        pypi_parser = subparsers.add_parser(
            "pypi",
            parents=[check_args_parser],
            help="Проверка доступа к PyPI и зеркалам",
            description="Команды для проверки доступности и производительности репозиториев PyPI.",
        )
        pypi_parser.set_defaults(handler=self.handle)

        pypi_subparsers = pypi_parser.add_subparsers(
            dest="subcommand", help="Доступные действия"
        )

        # pypi check
        pypi_subparsers.add_parser(
            "check",
            parents=[check_args_parser],
            help="Проверка доступности и скорости зеркал PyPI",
            description="Измеряет время отклика и скорость загрузки с зеркал PyPI.",
        )

    def handle(self, args: argparse.Namespace) -> None:
        """Обработчик команды pypi.

        Args:
            args: Объект Namespace с аргументами командной строки.
        """
        if not args.subcommand or args.subcommand == "check":
            self.handle_check(args)
        else:
            parser = argparse.ArgumentParser()
            subparsers = parser.add_subparsers()
            self.register(subparsers)
            parser.parse_args(["pypi", "--help"])

    def handle_check(self, args: argparse.Namespace) -> None:
        """Выполняет проверку доступности и скорости зеркал PyPI.

        Args:
            args: Объект Namespace с аргументами.
        """
        # Определяем консоли для логов и результатов
        log_console = self.err_console if args.json else self.console

        log_console.print("[INFO] Получение текущей конфигурации pip...")
        current_index = get_current_index_url()
        log_console.print(f"[INFO] Текущий index-url: [cyan]{current_index}[/cyan]")

        # Формируем список зеркал
        mirrors_to_check = [normalize_mirror_url(m) for m in DEFAULT_MIRRORS]

        norm_current = normalize_mirror_url(current_index)
        if norm_current not in mirrors_to_check:
            mirrors_to_check.append(norm_current)

        if args.mirrors:
            for m in args.mirrors.split(","):
                norm_m = normalize_mirror_url(m)
                if norm_m not in mirrors_to_check:
                    mirrors_to_check.append(norm_m)

        log_console.print(
            f"[INFO] Начинаем проверку {len(mirrors_to_check)} зеркал (пакет: [yellow]{args.package}[/yellow])...")

        results = []
        for mirror in mirrors_to_check:
            log_console.print(f" Проверка {mirror}...")
            res = measure_mirror(mirror, args.package)
            results.append(res)

        # Вывод результатов
        if args.json:
            best_mirror = find_best_mirror(results, current_index)
            output_data = {
                "current_index_url": current_index,
                "recommended_index_url": best_mirror,
                "results": results
            }
            # Печатаем строго в stdout (console) для корректного пайпинга
            self.console.print(json.dumps(output_data, indent=2, ensure_ascii=False))
            return

        # Интерактивный/красивый вывод таблицы
        use_rich = is_rich_enabled()
        if use_rich:
            from rich.table import Table

            table = Table(title="Результаты проверки зеркал PyPI", show_header=True, header_style="bold magenta")
            table.add_column("Зеркало (URL)", style="cyan", no_wrap=True)
            table.add_column("Статус", style="bold", justify="center")
            table.add_column("Пинг (мс)", justify="right")
            table.add_column("Скорость (КБ/с)", justify="right")

            for r in results:
                is_current = normalize_mirror_url(r["url"]) == norm_current
                url_str = r["url"]
                if is_current:
                    url_str += " [green](текущий)[/green]"

                if r["available"]:
                    status = "[green]Доступен[/green]"
                    latency = f"{r['latency_ms']:.1f}" if r["latency_ms"] is not None else "-"
                    speed = f"{r['download_speed_kbs']:.1f}" if r["download_speed_kbs"] is not None else "-"
                else:
                    status = f"[red]Ошибка[/red]"
                    latency = "-"
                    speed = "-"
                    if r["error"]:
                        status += f" ({r['error']})"

                table.add_row(url_str, status, latency, speed)

            self.console.print(table)
        else:
            # Текстовый fallback
            self.console.print("\n=== Результаты проверки зеркал PyPI ===")
            for r in results:
                is_current = normalize_mirror_url(r["url"]) == norm_current
                url_str = r["url"] + (" (текущий)" if is_current else "")
                if r["available"]:
                    latency = f"{r['latency_ms']:.1f} ms" if r["latency_ms"] is not None else "-"
                    speed = f"{r['download_speed_kbs']:.1f} KB/s" if r["download_speed_kbs"] is not None else "-"
                    self.console.print(f"- {url_str}: Доступен | Пинг: {latency} | Скорость: {speed}")
                else:
                    err = f" ({r['error']})" if r["error"] else ""
                    self.console.print(f"- {url_str}: Недоступен / Ошибка{err}")

        # Формируем и выводим рекомендации
        best_mirror = find_best_mirror(results, current_index)
        if best_mirror:
            self.console.print("\n[bold green]Рекомендация:[/bold green]")
            self.console.print(f"Зеркало [cyan]{best_mirror}[/cyan] работает значительно быстрее вашего текущего.")
            self.console.print(f"Вы можете переключиться на него, выполнив команду:")
            self.console.print(f"  [yellow]pip config set global.index-url {best_mirror}[/yellow]\n")
        else:
            self.console.print("\n[bold green]Рекомендация:[/bold green]")
            self.console.print(
                "Ваше текущее зеркало является оптимальным или разница в производительности незначительна.\n")
