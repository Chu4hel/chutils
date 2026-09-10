"""Адаптеры и фабрики конфигурации прокси для Playwright, Selenium и nodriver."""

from collections.abc import AsyncGenerator, Generator
from contextlib import asynccontextmanager, contextmanager
from typing import Literal

from chutils.scraping.proxy.extension import ChromeProxyExtension
from chutils.scraping.proxy.models import ProxyConfig
from chutils.scraping.proxy.parser import parse_proxy
from chutils.scraping.proxy.tunnel import AsyncProxyTunnel


def get_playwright_proxy(
    proxy: ProxyConfig | str | dict[str, object],
) -> dict[str, str]:
    """Формирует словарь параметров прокси для передачи в Playwright BrowserType.launch.

    Args:
        proxy: Конфигурация прокси (ProxyConfig, строка или dict).

    Returns:
        Словарь с параметрами server, username, password для Playwright.
    """
    cfg = parse_proxy(proxy)
    return cfg.to_playwright()


def get_selenium_proxy(
    proxy: ProxyConfig | str | dict[str, object],
    options: object | None = None,
) -> dict[str, str] | None:
    """Формирует параметры прокси для Selenium или добавляет их в переданный объект Options.

    Args:
        proxy: Конфигурация прокси (ProxyConfig, строка или dict).
        options: Опциональный экземпляр webdriver Options (например, ChromeOptions).

    Returns:
        Словарь capabilities прокси, если options не передан, иначе None.
    """
    cfg = parse_proxy(proxy)
    if options is not None and hasattr(options, "add_argument"):
        options.add_argument(cfg.to_chrome_arg())
        return None
    return cfg.to_selenium()


def get_nodriver_proxy_args(
    proxy: ProxyConfig | str | dict[str, object],
) -> list[str]:
    """Возвращает список аргументов запуска браузера для nodriver.

    Если прокси не требует авторизации, возвращает флаг `--proxy-server`.
    Если прокси требует авторизацию, генерирует Manifest v3 расширение через
    `ChromeProxyExtension` с авто-очисткой при завершении приложения.

    Args:
        proxy: Конфигурация прокси (ProxyConfig, строка или dict).

    Returns:
        Список флагов командной строки для запуска Chromium.
    """
    cfg = parse_proxy(proxy)
    if not cfg.has_auth:
        return [cfg.to_chrome_arg()]

    ext = ChromeProxyExtension(cfg, register_lifecycle_cleanup=True)
    return ext.get_chrome_args()


@contextmanager
def nodriver_proxy(
    proxy: ProxyConfig | str | dict[str, object],
) -> Generator[list[str], None, None]:
    """Контекстный менеджер аргументов запуска nodriver с авто-очисткой расширения.

    Args:
        proxy: Конфигурация прокси (ProxyConfig, строка или dict).

    Yields:
        Список флагов командной строки для nodriver.
    """
    cfg = parse_proxy(proxy)
    if not cfg.has_auth:
        yield [cfg.to_chrome_arg()]
    else:
        with ChromeProxyExtension(cfg, register_lifecycle_cleanup=False) as ext:
            yield ext.get_chrome_args()


@asynccontextmanager
async def async_nodriver_proxy(
    proxy: ProxyConfig | str | dict[str, object],
    mode: Literal["auto", "extension", "tunnel"] = "auto",
) -> AsyncGenerator[list[str], None]:
    """Асинхронный контекстный менеджер прокси для nodriver.

    Поддерживает режим авто-расширения (`extension`) или локального туннеля (`tunnel`).

    Args:
        proxy: Конфигурация прокси (ProxyConfig, строка или dict).
        mode: Режим проксирования ('auto', 'extension', 'tunnel').

    Yields:
        Список флагов командной строки для nodriver.
    """
    cfg = parse_proxy(proxy)
    if mode == "tunnel" or (mode == "auto" and cfg.protocol.startswith("socks")):
        async with AsyncProxyTunnel(cfg) as tunnel:
            yield [tunnel.to_chrome_arg()]
    else:
        if not cfg.has_auth:
            yield [cfg.to_chrome_arg()]
        else:
            with ChromeProxyExtension(cfg, register_lifecycle_cleanup=False) as ext:
                yield ext.get_chrome_args()
