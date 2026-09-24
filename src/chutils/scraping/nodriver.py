"""Фабрики и контекстные менеджеры для запуска браузера nodriver с антидетектом."""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from chutils.lifecycle import register_cleanup
from chutils.logger import setup_logger
from chutils.scraping.humanize.antidetect import get_browser_launch_args
from chutils.scraping.humanize.config import AntidetectConfig
from chutils.scraping.profiles.hygiene import sanitize_profile
from chutils.scraping.proxy.adapters import get_nodriver_proxy_args
from chutils.scraping.proxy.models import ProxyConfig

logger = setup_logger(__name__)


def _get_nodriver_module() -> Any:
    """Безопасно импортирует библиотеку nodriver.

    Returns:
        Модуль nodriver.

    Raises:
        ImportError: Если nodriver не установлен.
    """
    try:
        import nodriver as uc

        return uc
    except ImportError as err:
        raise ImportError(
            "Для использования nodriver необходимо установить библиотеку: "
            "pip install nodriver или pip install chutils[scraping]"
        ) from err


async def close_tab(tab: Any, *, timeout: float = 3.0) -> None:
    """Безопасно закрывает вкладку nodriver с защитой от зависания CDP-сокета.

    Если вкладка потерпела крах (Renderer Crash) или CDP не отвечает,
    операция прерывается по истечении таймаута без зависания вызывающего потока.

    Args:
        tab: Объект вкладки nodriver (nodriver.Tab).
        timeout: Максимальное время ожидания закрытия вкладки в секундах.
    """
    close_method = getattr(tab, "close", None)
    if callable(close_method):
        res = close_method()
        if inspect.isawaitable(res):
            try:
                await asyncio.wait_for(res, timeout=timeout)
            except TimeoutError:
                logger.debug(
                    f"Таймаут ({timeout}с) при закрытии вкладки nodriver, принудительное завершение."
                )
            except Exception as exc:
                logger.debug(f"Ошибка при закрытии вкладки nodriver: {exc}")


async def launch_nodriver(
    config: AntidetectConfig | None = None,
    *,
    user_data_dir: Path | str | None = None,
    browser_executable_path: Path | str | None = None,
    proxy: ProxyConfig | str | dict[str, object] | None = None,
    headless: bool = False,
    browser_args: list[str] | None = None,
    apply_config_to_tab: bool = True,
    sanitize_profile_dir: bool = True,
    **kwargs: Any,
) -> Any:
    """Запускает браузер nodriver с рекомендуемыми стелс-аргументами и AntidetectConfig.

    Args:
        config: Экземпляр AntidetectConfig. Если None, используется AntidetectConfig.preset_stealth_nodriver().
        user_data_dir: Путь к постоянному каталогу профиля браузера (куки, сессии, история).
        browser_executable_path: Пользовательский путь к бинарному файлу Chromium/Chrome/Brave.
        proxy: Настройки прокси (строка, ProxyConfig или dict). Если требуется авторизация,
            автоматически создается временное Manifest v3 расширение.
        headless: Флаг запуска в фоновом (headless) режиме.
        browser_args: Дополнительные аргументы командной строки Chromium.
        apply_config_to_tab: Если True, автоматически применяет конфигурацию антидетекта к первой вкладке.
        sanitize_profile_dir: Если True и передан user_data_dir, перед запуском браузера сбрасывает флаги
            аварийного завершения (exit_type="Normal") и очищает остаточные сессии/вкладки,
            предотвращая инфобар восстановления вкладок и детекты антифрода.
        **kwargs: Дополнительные параметры для передачи в nodriver.start().

    Returns:
        Экземпляр nodriver.Browser.
    """
    uc = _get_nodriver_module()

    if config is None:
        config = AntidetectConfig.preset_stealth_nodriver()

    # Сборка базовых стелс-аргументов запуска
    recommended_args = get_browser_launch_args()

    merged_args: list[str] = list(recommended_args)

    # Интеграция прокси
    if proxy is not None:
        proxy_args = get_nodriver_proxy_args(proxy)
        for p_arg in proxy_args:
            if p_arg not in merged_args:
                merged_args.append(p_arg)

    # Пользовательские аргументы
    if browser_args:
        for b_arg in browser_args:
            if b_arg not in merged_args:
                merged_args.append(b_arg)

    # Очистка профиля от следов падений и сброс crash flags перед запуском
    if sanitize_profile_dir and user_data_dir is not None:
        try:
            sanitize_profile(user_data_dir)
        except Exception as exc:
            logger.debug(f"Не удалось выполнить sanitize_profile для {user_data_dir}: {exc}")

    # Запуск браузера
    start_kwargs: dict[str, Any] = dict(kwargs)
    if user_data_dir is not None:
        start_kwargs["user_data_dir"] = str(user_data_dir)
    if browser_executable_path is not None:
        start_kwargs["browser_executable_path"] = str(browser_executable_path)

    browser = await uc.start(
        browser_args=merged_args,
        headless=headless,
        **start_kwargs,
    )

    # Регистрация очистки в жизненном цикле
    def _cleanup_browser() -> None:
        try:
            stop_method = getattr(browser, "stop", None)
            if callable(stop_method):
                res = stop_method()
                if inspect.iscoroutine(res):
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(res)
                    except RuntimeError:
                        pass

        except Exception:
            pass

    register_cleanup(_cleanup_browser)

    # Применение AntidetectConfig к открытой вкладке
    if apply_config_to_tab:
        tab = getattr(browser, "main_tab", None)
        if tab is None:
            tabs = getattr(browser, "tabs", [])
            if tabs:
                tab = tabs[0]

        if tab is not None:
            try:
                await config.apply_to_nodriver(tab)
            except Exception as exc:
                logger.debug(
                    f"Не удалось применить AntidetectConfig к вкладке nodriver: {exc}"
                )

    return browser


@asynccontextmanager
async def nodriver_session(
    config: AntidetectConfig | None = None,
    *,
    user_data_dir: Path | str | None = None,
    browser_executable_path: Path | str | None = None,
    proxy: ProxyConfig | str | dict[str, object] | None = None,
    headless: bool = False,
    browser_args: list[str] | None = None,
    apply_config_to_tab: bool = True,
    sanitize_profile_dir: bool = True,
    **kwargs: Any,
) -> AsyncIterator[Any]:
    """Асинхронный контекстный менеджер сессии браузера nodriver с гарантированным закрытием.

    Args:
        config: Экземпляр AntidetectConfig. Если None, используется AntidetectConfig.preset_stealth_nodriver().
        user_data_dir: Путь к постоянному каталогу профиля браузера (куки, сессии, история).
        browser_executable_path: Пользовательский путь к бинарному файлу Chromium/Chrome/Brave.
        proxy: Настройки прокси.
        headless: Флаг запуска в headless режиме.
        browser_args: Дополнительные флаги Chromium.
        apply_config_to_tab: Автоматически применить AntidetectConfig к вкладке.
        sanitize_profile_dir: Выполнить санитайзинг профиля перед запуском.
        **kwargs: Дополнительные параметры nodriver.start().

    Yields:
        Экземпляр nodriver.Browser.
    """
    browser = await launch_nodriver(
        config=config,
        user_data_dir=user_data_dir,
        browser_executable_path=browser_executable_path,
        proxy=proxy,
        headless=headless,
        browser_args=browser_args,
        apply_config_to_tab=apply_config_to_tab,
        sanitize_profile_dir=sanitize_profile_dir,
        **kwargs,
    )
    try:
        yield browser
    finally:
        stop_method = getattr(browser, "stop", None)
        if callable(stop_method):
            res = stop_method()
            if inspect.isawaitable(res):
                try:
                    await asyncio.wait_for(res, timeout=5.0)
                except TimeoutError:
                    logger.debug(
                        "Таймаут (5.0с) при остановке браузера nodriver, принудительное завершение."
                    )
                except Exception as exc:
                    logger.debug(f"Ошибка при остановке браузера nodriver: {exc}")


__all__ = [
    "close_tab",
    "launch_nodriver",
    "nodriver_session",
]
