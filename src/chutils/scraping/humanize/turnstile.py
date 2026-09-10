"""Модуль автоматического обнаружения и решения Cloudflare Turnstile капчи."""

from __future__ import annotations

import asyncio
import inspect
import random
import time
from typing import Any

from chutils.logger import setup_logger

from .actions import async_click, async_human_sleep
from .antidetect import extract_clearance_cookies

logger = setup_logger(__name__)

TURNSTILE_INSPECT_JS = """(function() {
    // 1. Проверка наличия решения через token input
    const responseInputs = document.querySelectorAll(
        'input[name="cf-turnstile-response"], [name="cf_challenge_response"], input[id*="turnstile"][name*="response"]'
    );
    for (const inp of responseInputs) {
        if (inp && inp.value && inp.value.trim().length > 10) {
            return { found: true, solved: true, token: inp.value.trim() };
        }
    }

    // 2. Поиск интерактивного iframe Turnstile
    const iframe = document.querySelector('iframe[src*="challenges.cloudflare.com"], iframe[src*="turnstile"]');
    if (iframe) {
        const rect = iframe.getBoundingClientRect();
        return {
            found: true,
            solved: false,
            type: 'iframe',
            x: rect.x + window.scrollX,
            y: rect.y + window.scrollY,
            width: rect.width,
            height: rect.height,
            visible: rect.width > 20 && rect.height > 20
        };
    }

    // 3. Поиск контейнера виджета Turnstile
    const container = document.querySelector('.cf-turnstile, #turnstile-wrapper, [data-sitekey]');
    if (container) {
        const rect = container.getBoundingClientRect();
        return {
            found: true,
            solved: false,
            type: 'container',
            x: rect.x + window.scrollX,
            y: rect.y + window.scrollY,
            width: rect.width,
            height: rect.height,
            visible: rect.width > 20 && rect.height > 20
        };
    }

    return null;
})();"""


async def _evaluate_js(tab: Any, script: str) -> Any:
    """Выполняет JavaScript в контексте nodriver Tab или Playwright Page."""
    eval_method = getattr(tab, "evaluate", None)
    if not callable(eval_method):
        return None

    res = eval_method(script)
    if inspect.isawaitable(res):
        return await res
    return res


async def detect_cf_turnstile(tab: Any) -> dict[str, Any] | None:
    """Обнаруживает присутствие и координаты виджета Cloudflare Turnstile.

    Args:
        tab: Объект вкладки nodriver Tab или Playwright Page.

    Returns:
        Словарь с параметрами виджета ('found', 'solved', 'x', 'y', 'width', 'height')
        либо None, если Turnstile не найден.
    """
    try:
        raw_res = await _evaluate_js(tab, TURNSTILE_INSPECT_JS)
        if isinstance(raw_res, dict) and raw_res.get("found"):
            return raw_res
    except Exception as exc:
        logger.debug(f"Ошибка при инспекции Turnstile: {exc}")
    return None


async def is_cf_turnstile_solved(tab: Any) -> bool:
    """Проверяет, решен ли челендж Cloudflare Turnstile в сессии.

    Args:
        tab: Объект вкладки nodriver Tab или Playwright Page.

    Returns:
        True, если в DOM присутствует токен ответа или установлена cookie cf_clearance.
    """
    detect_res = await detect_cf_turnstile(tab)
    if detect_res and detect_res.get("solved"):
        return True

    # Проверка наличия cookies cf_clearance
    try:
        cookies_data = extract_clearance_cookies(tab)
        if inspect.isawaitable(cookies_data):
            cookies_data = await cookies_data
        if isinstance(cookies_data, dict):
            cookies_dict = cookies_data.get("cookies", {})
            if "cf_clearance" in cookies_dict:
                return True
    except Exception:
        pass

    return False


async def solve_cf_turnstile(
    tab: Any,
    *,
    timeout: float = 15.0,
    check_interval: float = 0.5,
    click_delay: tuple[float, float] = (0.5, 1.2),
    raise_on_failure: bool = False,
) -> bool:
    """Автоматически обнаруживает и решает капчу Cloudflare Turnstile.

    Находит интерактивную область чекбокса, выполняет реалистичное наведение
    курсора мыши по кривой Безье/WindMouse и клик, после чего ожидает
    получения токена валидации.

    Args:
        tab: Объект вкладки nodriver Tab или Playwright Page.
        timeout: Максимальное время ожидания решения капчи в секундах.
        check_interval: Интервал проверки состояния капчи в секундах.
        click_delay: Задержка перед кликом после наведения (min, max).
        raise_on_failure: Если True, при таймауте выбрасывает RuntimeError.

    Returns:
        True, если капча успешно решена, иначе False.

    Raises:
        RuntimeError: Если raise_on_failure=True и капча не была решена за время таймаута.
    """
    start_time = time.monotonic()
    clicked = False

    logger.debug("Начало ожидания и решения Cloudflare Turnstile...")

    while time.monotonic() - start_time < timeout:
        # Проверка 1: капча уже решена?
        if await is_cf_turnstile_solved(tab):
            logger.info("Cloudflare Turnstile успешно решен.")
            return True

        # Проверка 2: обнаружен ли виджет Turnstile для клика?
        info = await detect_cf_turnstile(tab)
        if info and not clicked and info.get("visible"):
            x = float(info.get("x", 0.0))
            y = float(info.get("y", 0.0))
            width = float(info.get("width", 300.0))
            height = float(info.get("height", 65.0))

            # Чекбокс Turnstile обычно располагается в левой части виджета
            # Смещение X ~ 25-45px, Y по центру (~ height / 2)
            offset_x = min(width * 0.12, 35.0) + random.uniform(-3.0, 3.0)
            offset_y = (height / 2.0) + random.uniform(-4.0, 4.0)

            target_x = max(1, int(x + offset_x))
            target_y = max(1, int(y + offset_y))

            logger.debug(
                f"Обнаружен Turnstile виджет ({info.get('type')}), "
                f"координаты клика: ({target_x}, {target_y})"
            )

            # Человекоподобная микропауза перед кликом
            if click_delay and click_delay[0] > 0:
                await async_human_sleep(click_delay[0], click_delay[1])

            try:
                await async_click(
                    tab,
                    x=target_x,
                    y=target_y,
                    algorithm="windmouse",
                    hold_time=(0.06, 0.14),
                )
                clicked = True
                logger.debug("Клик по чекбоксу Turnstile выполнен.")
            except Exception as click_err:
                logger.debug(f"Ошибка при клике по Turnstile: {click_err}")

        await asyncio.sleep(check_interval)

    # Финальная проверка после завершения цикла
    if await is_cf_turnstile_solved(tab):
        logger.info("Cloudflare Turnstile успешно решен.")
        return True

    if raise_on_failure:
        raise RuntimeError(
            f"Не удалось решить Cloudflare Turnstile за отведенное время ({timeout} сек.)."
        )

    logger.warning(f"Таймаут ожидания решения Cloudflare Turnstile ({timeout} сек.).")
    return False
