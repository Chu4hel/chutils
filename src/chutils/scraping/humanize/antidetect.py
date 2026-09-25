from __future__ import annotations

import importlib.util
import inspect
import re
import sys
from typing import Any

from chutils.exceptions import OptionalDependencyError

from .antidetect_scripts import (
    DEFAULT_DEVICE_MEMORY,
    DEFAULT_HARDWARE_CONCURRENCY,
    DEFAULT_WEBGL_RENDERER,
    DEFAULT_WEBGL_VENDOR,
    _get_antidetect_js,
)
from .config import AntidetectConfig


def get_client_hints(user_agent: str | None = None) -> dict[str, Any]:
    """Генерирует словарь согласованных Client Hints (navigator.userAgentData) на основе User-Agent.

    Args:
        user_agent: Строка User-Agent. Если None, используется стандартный Chrome на Windows.

    Returns:
        Словарь с параметрами Client Hints: platform, mobile, brands.
    """
    ua = user_agent or (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    platform = "Windows"
    if "Macintosh" in ua or "Mac OS X" in ua:
        platform = "macOS"
    elif "Android" in ua:
        platform = "Android"
    elif "Linux" in ua:
        platform = "Linux"
    elif "iPhone" in ua or "iPad" in ua:
        platform = "iOS"

    mobile = platform in ("Android", "iOS") or "Mobile" in ua

    # Извлечение версии Chrome
    chrome_match = re.search(r"Chrome/(\d+)", ua)
    chrome_version = chrome_match.group(1) if chrome_match else "120"

    brands = [
        {"brand": "Not_A Brand", "version": "8"},
        {"brand": "Chromium", "version": chrome_version},
        {"brand": "Google Chrome", "version": chrome_version},
    ]

    return {
        "platform": platform,
        "mobile": mobile,
        "brands": brands,
    }


ANTIDETECT_JS_SCRIPT = _get_antidetect_js(
    DEFAULT_WEBGL_VENDOR,
    DEFAULT_WEBGL_RENDERER,
    DEFAULT_HARDWARE_CONCURRENCY,
    DEFAULT_DEVICE_MEMORY,
)
"""JavaScript-инъекция для скрытия признаков автоматизации браузера (webdriver, Canvas WebGL и др.) с настройками по умолчанию."""


def _ensure_playwright() -> None:
    if "playwright" in sys.modules:
        return
    try:
        if importlib.util.find_spec("playwright") is None:
            raise ImportError()
    except (ImportError, ValueError):
        raise OptionalDependencyError(
            "Для использования Playwright-функций требуется библиотека 'playwright'.\n"
            "Установите её: pip install chutils[scraping]",
            dependency="playwright",
            hint="Выполните pip install chutils[scraping]",
        )


def _ensure_selenium() -> None:
    if "selenium" in sys.modules:
        return
    try:
        if importlib.util.find_spec("selenium") is None:
            raise ImportError()
    except (ImportError, ValueError):
        raise OptionalDependencyError(
            "Для использования Selenium-функций требуется библиотека 'selenium'.\n"
            "Установите её: pip install chutils[scraping]",
            dependency="selenium",
            hint="Выполните pip install chutils[scraping]",
        )


def _ensure_nodriver() -> None:
    if "nodriver" in sys.modules:
        return
    try:
        if importlib.util.find_spec("nodriver") is None:
            raise ImportError()
    except (ImportError, ValueError):
        raise OptionalDependencyError(
            "Для использования nodriver-функций требуется библиотека 'nodriver'.\n"
            "Установите её: pip install nodriver",
            dependency="nodriver",
            hint="Выполните pip install nodriver",
        )


async def apply_antidetect_playwright(
    context: Any,
    *,
    config: AntidetectConfig | None = None,
    webgl_vendor: str = DEFAULT_WEBGL_VENDOR,
    webgl_renderer: str = DEFAULT_WEBGL_RENDERER,
    hardware_concurrency: int = DEFAULT_HARDWARE_CONCURRENCY,
    device_memory: int = DEFAULT_DEVICE_MEMORY,
    stealth_minimal: bool = False,
    session_seed: str | int = 1337,
    client_hints: dict[str, Any] | None = None,
    user_agent: str | None = None,
) -> None:
    """Применяет JS-инъекции анти-детекта к контексту Playwright.

    Args:
        context: Объект контекста Playwright BrowserContext.
        config: Экземпляр AntidetectConfig (если указан, параметры берутся из него).
        webgl_vendor: Подменяемый производитель WebGL.
        webgl_renderer: Подменяемая видеокарта WebGL.
        hardware_concurrency: Эмулируемое количество ядер процессора.
        device_memory: Эмулируемый объем оперативной памяти в ГБ.
        stealth_minimal: Если True, не накладывать синтетический шум на Canvas и не подменять WebGL.
        session_seed: Сид для детерминированного шума Canvas.
        client_hints: Дополнительные параметры Client Hints (navigator.userAgentData).
        user_agent: Пользовательская строка User-Agent.
    """
    _ensure_playwright()
    if config is not None:
        webgl_vendor = config.webgl_vendor
        webgl_renderer = config.webgl_renderer
        hardware_concurrency = config.hardware_concurrency
        device_memory = config.device_memory
        stealth_minimal = config.stealth_minimal
        session_seed = config.session_seed
        client_hints = config.client_hints
        if config.user_agent is not None:
            user_agent = config.user_agent

    script = (
        config.get_init_script()
        if config is not None
        else _get_antidetect_js(
            webgl_vendor=webgl_vendor,
            webgl_renderer=webgl_renderer,
            hardware_concurrency=hardware_concurrency,
            device_memory=device_memory,
            stealth_minimal=stealth_minimal,
            session_seed=session_seed,
            client_hints=client_hints,
        )
    )
    await context.add_init_script(script)


def apply_antidetect_selenium(
    driver: Any,
    *,
    config: AntidetectConfig | None = None,
    webgl_vendor: str = DEFAULT_WEBGL_VENDOR,
    webgl_renderer: str = DEFAULT_WEBGL_RENDERER,
    hardware_concurrency: int = DEFAULT_HARDWARE_CONCURRENCY,
    device_memory: int = DEFAULT_DEVICE_MEMORY,
    stealth_minimal: bool = False,
    session_seed: str | int = 1337,
    client_hints: dict[str, Any] | None = None,
    user_agent: str | None = None,
) -> None:
    """Применяет JS-инъекции анти-детекта к сессии Selenium.

    Args:
        driver: Экземпляр Selenium WebDriver.
        config: Экземпляр AntidetectConfig (если указан, параметры берутся из него).
        webgl_vendor: Подменяемый производитель WebGL.
        webgl_renderer: Подменяемая видеокарта WebGL.
        hardware_concurrency: Эмулируемое количество ядер процессора.
        device_memory: Эмулируемый объем оперативной памяти в ГБ.
        stealth_minimal: Если True, не накладывать синтетический шум на Canvas и не подменять WebGL.
        session_seed: Сид для детерминированного шума Canvas.
        client_hints: Дополнительные параметры Client Hints (navigator.userAgentData).
        user_agent: Пользовательская строка User-Agent.
    """
    _ensure_selenium()
    if config is not None:
        webgl_vendor = config.webgl_vendor
        webgl_renderer = config.webgl_renderer
        hardware_concurrency = config.hardware_concurrency
        device_memory = config.device_memory
        stealth_minimal = config.stealth_minimal
        session_seed = config.session_seed
        client_hints = config.client_hints
        if config.user_agent is not None:
            user_agent = config.user_agent

    script = (
        config.get_init_script()
        if config is not None
        else _get_antidetect_js(
            webgl_vendor=webgl_vendor,
            webgl_renderer=webgl_renderer,
            hardware_concurrency=hardware_concurrency,
            device_memory=device_memory,
            stealth_minimal=stealth_minimal,
            session_seed=session_seed,
            client_hints=client_hints,
        )
    )
    if hasattr(driver, "execute_cdp_cmd"):
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument", {"source": script}
        )
        if user_agent:
            driver.execute_cdp_cmd(
                "Emulation.setUserAgentOverride", {"userAgent": user_agent}
            )
        if config is not None and config.screen_width and config.screen_height:
            try:
                driver.execute_cdp_cmd(
                    "Emulation.setDeviceMetricsOverride",
                    {
                        "width": config.screen_width,
                        "height": config.screen_height,
                        "deviceScaleFactor": config.device_pixel_ratio or 1.0,
                        "mobile": False,
                    },
                )
            except Exception:
                pass
    else:
        driver.execute_script(script)


async def apply_antidetect_nodriver(
    tab: Any,
    *,
    config: AntidetectConfig | None = None,
    webgl_vendor: str = DEFAULT_WEBGL_VENDOR,
    webgl_renderer: str = DEFAULT_WEBGL_RENDERER,
    hardware_concurrency: int = DEFAULT_HARDWARE_CONCURRENCY,
    device_memory: int = DEFAULT_DEVICE_MEMORY,
    stealth_minimal: bool = True,
    session_seed: str | int = 1337,
    client_hints: dict[str, Any] | None = None,
    user_agent: str | None = None,
) -> None:
    """Применяет JS-инъекции анти-детекта к вкладке (Tab) nodriver.

    По умолчанию stealth_minimal=True для сохранения естественного отпечатка
    реального Chromium и предотвращения детекта искусственного шума Canvas/WebGL.

    Args:
        tab: Объект вкладки nodriver Tab.
        config: Экземпляр AntidetectConfig (если указан, параметры берутся из него).
        webgl_vendor: Подменяемый производитель WebGL.
        webgl_renderer: Подменяемая видеокарта WebGL.
        hardware_concurrency: Эмулируемое количество ядер процессора.
        device_memory: Эмулируемый объем оперативной памяти в ГБ.
        stealth_minimal: Если True, не накладывать синтетический шум на Canvas и не подменять WebGL,
            сохраняя естественный отпечаток установленного браузера Google Chrome (True по умолчанию).
        session_seed: Сид для детерминированного шума Canvas.
        client_hints: Дополнительные параметры Client Hints (navigator.userAgentData).
        user_agent: Пользовательская строка User-Agent для переопределения через CDP.
    """
    _ensure_nodriver()
    from nodriver.cdp import emulation, page

    if config is not None:
        webgl_vendor = config.webgl_vendor
        webgl_renderer = config.webgl_renderer
        hardware_concurrency = config.hardware_concurrency
        device_memory = config.device_memory
        stealth_minimal = config.stealth_minimal
        session_seed = config.session_seed
        client_hints = config.client_hints
        if config.user_agent is not None:
            user_agent = config.user_agent

    # 1. Переопределение User-Agent через CDP Emulation для синхронизации с Client Hints и HTTP заголовками
    if user_agent:
        try:
            await tab.send(emulation.set_user_agent_override(user_agent=user_agent))
        except Exception:
            pass

    # 2. Эмуляция реальных метрик экрана и viewport через CDP Emulation (предотвращает детекцию CSS Media Queries)
    if config is not None and config.screen_width and config.screen_height:
        try:
            await tab.send(
                emulation.set_device_metrics_override(
                    width=config.screen_width,
                    height=config.screen_height,
                    device_scale_factor=config.device_pixel_ratio or 1.0,
                    mobile=False,
                )
            )
        except Exception:
            pass

    script = (
        config.get_init_script()
        if config is not None
        else _get_antidetect_js(
            webgl_vendor=webgl_vendor,
            webgl_renderer=webgl_renderer,
            hardware_concurrency=hardware_concurrency,
            device_memory=device_memory,
            stealth_minimal=stealth_minimal,
            session_seed=session_seed,
            client_hints=client_hints,
        )
    )
    # Двойная инъекция:
    # 3. Регистрация на новые документы (будущие навигации, редиректы, перезагрузки)
    await tab.send(page.add_script_to_evaluate_on_new_document(source=script))

    # 4. Мгновенное применение к уже открытой текущей странице (если вкладка активна)
    if hasattr(tab, "evaluate") and callable(tab.evaluate):
        try:
            await tab.evaluate(script)
        except Exception:
            pass


def get_browser_launch_args(*, no_sandbox: bool = False) -> list[str]:
    """Возвращает расширенный набор аргументов запуска браузера для скрытия автоматизации.

    Предотвращает появление инфобаров, системных всплывающих окон Chromium о падениях
    и некорректном завершении сессий.

    Note:
        Флаг ``--no-sandbox`` по умолчанию отключен (False), так как отключение песочницы
        является первичным триггером для многих систем антифрода (Cloudflare, Google Cloud Armor)
        и снижает безопасность. Если запуск производится внутри изолированного Docker-контейнера
        без прав root/SYS_ADMIN, передайте ``no_sandbox=True``.

        Флаги ``--disable-blink-features=AutomationControlled``, ``--use-fake-ui-for-media-stream``
        и подобные намеренно исключены, так как в современных версиях Chromium они
        вызывают системный инфобар о неподдерживаемых флагах или детектируются
        антибот-системами. Скрытие ``navigator.webdriver`` выполняется через
        CDP-инъекцию скрипта антидетекта.

    Args:
        no_sandbox: Если True, добавляет флаг ``--no-sandbox`` (рекомендуется только для root Docker-контейнеров).

    Returns:
        Список аргументов командной строки запуска браузера.
    """
    args = [
        "--disable-dev-shm-usage",
        "--no-first-run",
        "--no-default-browser-check",
        "--password-store=basic",
        "--lang=en-US,en;q=0.9",
        "--mute-audio",
        "--disable-background-timer-throttling",
        "--disable-component-update",
        "--disable-session-crashed-bubble",
        "--hide-crash-restore-bubble",
        "--restore-last-session=false",
        "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
        "--enforce-webrtc-ip-permission-check",
    ]
    if no_sandbox:
        args.insert(0, "--no-sandbox")
    return args



async def _extract_clearance_cookies_async(target: Any) -> dict[str, Any]:
    """Асинхронное извлечение кук и user-agent из Playwright / Nodriver."""
    cookies_dict: dict[str, str] = {}
    ua: str = ""

    send_method = getattr(target, "send", None)
    is_nodriver = callable(send_method) and inspect.iscoroutinefunction(send_method)

    if is_nodriver:
        # Nodriver Tab
        try:
            from nodriver.cdp import network

            cmd_res = await target.send(network.get_cookies())
            raw_cookies = getattr(cmd_res, "cookies", [])
            for c in raw_cookies:
                if isinstance(c, dict):
                    c_name = c.get("name")
                    c_val = c.get("value")
                else:
                    c_name = getattr(c, "name", None)
                    c_val = getattr(c, "value", None)
                if c_name and c_val:
                    cookies_dict[str(c_name)] = str(c_val)
        except Exception:
            pass

        evaluate_method = getattr(target, "evaluate", None)
        if callable(evaluate_method):
            try:
                res = evaluate_method("navigator.userAgent")
                ua = await res if inspect.isawaitable(res) else str(res)
            except Exception:
                ua = ""
    else:
        # Playwright Page / BrowserContext
        cookies_method = None
        context_attr = getattr(target, "context", None)
        if context_attr is not None and hasattr(context_attr, "cookies"):
            cookies_method = getattr(context_attr, "cookies", None)
        elif hasattr(target, "cookies"):
            cookies_method = getattr(target, "cookies", None)

        if callable(cookies_method):
            raw_cookies = cookies_method()
            if inspect.isawaitable(raw_cookies):
                raw_cookies = await raw_cookies
            for c in raw_cookies:
                if isinstance(c, dict) and "name" in c and "value" in c:
                    cookies_dict[c["name"]] = c["value"]

        evaluate_method = getattr(target, "evaluate", None)
        if callable(evaluate_method):
            try:
                res = evaluate_method("navigator.userAgent")
                ua = await res if inspect.isawaitable(res) else str(res)
            except Exception:
                ua = ""

    return {"cookies": cookies_dict, "user_agent": ua}


def _extract_clearance_cookies_sync(target: Any) -> dict[str, Any]:
    """Синхронное извлечение кук и user-agent из Selenium WebDriver."""
    cookies_dict: dict[str, str] = {}
    ua: str = ""

    if hasattr(target, "get_cookies") and callable(target.get_cookies):
        raw_cookies = target.get_cookies()
        for c in raw_cookies:
            if isinstance(c, dict) and "name" in c and "value" in c:
                cookies_dict[c["name"]] = c["value"]

    if hasattr(target, "execute_script") and callable(target.execute_script):
        try:
            ua = str(target.execute_script("return navigator.userAgent;"))
        except Exception:
            ua = ""

    return {"cookies": cookies_dict, "user_agent": ua}


def extract_clearance_cookies(target: Any) -> Any:
    """Извлекает cookies (включая cf_clearance) и User-Agent из сессии браузера.

    Поддерживает Playwright Page/BrowserContext (асинхронно), Nodriver Tab (асинхронно)
    и Selenium WebDriver (синхронно).

    Args:
        target: Экземпляр Playwright (Page, Context), Selenium WebDriver или Nodriver Tab.

    Returns:
        Словарь вида {'cookies': {'cf_clearance': '...', ...}, 'user_agent': '...'},
        либо корутина, возвращающая данный словарь.
    """
    send_method = getattr(target, "send", None)
    context_attr = getattr(target, "context", None)
    cookies_method = (
        getattr(context_attr, "cookies", None)
        if context_attr
        else getattr(target, "cookies", None)
    )

    is_async = (callable(send_method) and inspect.iscoroutinefunction(send_method)) or (
        callable(cookies_method) and inspect.iscoroutinefunction(cookies_method)
    )

    if not is_async and hasattr(target, "get_cookies"):
        return _extract_clearance_cookies_sync(target)

    # Для асинхронных драйверов (Playwright, Nodriver)
    return _extract_clearance_cookies_async(target)


__all__ = [
    "ANTIDETECT_JS_SCRIPT",
    "DEFAULT_DEVICE_MEMORY",
    "DEFAULT_HARDWARE_CONCURRENCY",
    "DEFAULT_WEBGL_RENDERER",
    "DEFAULT_WEBGL_VENDOR",
    "_get_antidetect_js",
    "apply_antidetect_nodriver",
    "apply_antidetect_playwright",
    "apply_antidetect_selenium",
    "extract_clearance_cookies",
    "get_browser_launch_args",
    "get_client_hints",
]
