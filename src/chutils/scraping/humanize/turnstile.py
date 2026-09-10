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
    // 0. Рекурсивный поиск элементов с учетом открытых shadowRoot
    function findElementsDeep(root, selector) {
        let results = [];
        if (!root) return results;
        try {
            const matches = root.querySelectorAll(selector);
            for (let i = 0; i < matches.length; i++) {
                results.push(matches[i]);
            }
        } catch (e) {}
        try {
            const children = root.querySelectorAll('*');
            for (let i = 0; i < children.length; i++) {
                const child = children[i];
                if (child && child.shadowRoot) {
                    results = results.concat(findElementsDeep(child.shadowRoot, selector));
                }
            }
        } catch (e) {}
        return results;
    }

    // 1. Проверка наличия решения через token input
    const responseInputs = findElementsDeep(
        document,
        'input[name="cf-turnstile-response"], [name="cf_challenge_response"], input[id*="turnstile"][name*="response"]'
    );
    for (let i = 0; i < responseInputs.length; i++) {
        const inp = responseInputs[i];
        if (inp && inp.value && inp.value.trim().length > 10) {
            return { found: true, solved: true, token: inp.value.trim() };
        }
    }

    // 2. Поиск кандидатов: интерактивный iframe или контейнер Turnstile
    const iframes = findElementsDeep(document, 'iframe[src*="challenges.cloudflare.com"], iframe[src*="turnstile"]');
    const containers = findElementsDeep(document, '.cf-turnstile, #turnstile-wrapper, [data-sitekey]');
    const candidates = iframes.concat(containers);

    for (let i = 0; i < candidates.length; i++) {
        const el = candidates[i];
        if (!el) continue;

        const style = window.getComputedStyle(el);
        const isHidden = (
            style.display === 'none' ||
            style.visibility === 'hidden' ||
            parseFloat(style.opacity || '1') < 0.1 ||
            style.pointerEvents === 'none'
        );

        // Прокрутка элемента в центр видимой области экрана (Client Viewport)
        if (typeof el.scrollIntoView === 'function') {
            try {
                el.scrollIntoView({ block: 'center', inline: 'center', behavior: 'instant' });
            } catch (e) {
                try { el.scrollIntoView(); } catch (e2) {}
            }
        }

        const rect = el.getBoundingClientRect();
        const isVisible = !isHidden && rect.width >= 20 && rect.height >= 20;

        // Проверка состояния интерактивности виджета (не спиннер / checking)
        const stateAttr = el.getAttribute('data-state') || '';
        const isChecking = stateAttr === 'checking' || stateAttr === 'verifying';
        const isInteractive = isVisible && !isChecking;

        const isIframe = el.tagName && el.tagName.toLowerCase() === 'iframe';

        return {
            found: true,
            solved: false,
            type: isIframe ? 'iframe' : 'container',
            x: rect.left,
            y: rect.top,
            width: rect.width,
            height: rect.height,
            visible: isVisible,
            interactive: isInteractive,
            data_state: stateAttr
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


async def _detect_cf_turnstile_cdp_fallback(tab: Any) -> dict[str, Any] | None:
    """Fallback-поиск виджета через CDP методы вкладки (nodriver Tab.find / get_position)."""
    find_method = getattr(tab, "find", None)
    if not callable(find_method):
        return None

    selectors = [
        "iframe[src*='challenges.cloudflare.com']",
        "iframe[src*='turnstile']",
        ".cf-turnstile",
        "#turnstile-wrapper",
    ]

    for sel in selectors:
        try:
            res = find_method(sel)
            if inspect.isawaitable(res):
                el = await res
            else:
                el = res

            if el is None:
                continue

            get_pos = getattr(el, "get_position", None)
            if callable(get_pos):
                pos_res = get_pos()
                if inspect.isawaitable(pos_res):
                    pos = await pos_res
                else:
                    pos = pos_res

                if (
                    pos
                    and getattr(pos, "width", 0) >= 20
                    and getattr(pos, "height", 0) >= 20
                ):
                    return {
                        "found": True,
                        "solved": False,
                        "type": "iframe" if "iframe" in sel else "container",
                        "x": float(getattr(pos, "x", 0.0)),
                        "y": float(getattr(pos, "y", 0.0)),
                        "width": float(getattr(pos, "width", 300.0)),
                        "height": float(getattr(pos, "height", 65.0)),
                        "visible": True,
                        "interactive": True,
                    }
        except Exception as exc:
            logger.debug(f"CDP fallback error for {sel}: {exc}")
    return None


async def detect_cf_turnstile(tab: Any) -> dict[str, Any] | None:
    """Обнаруживает присутствие и координаты виджета Cloudflare Turnstile.

    Args:
        tab: Объект вкладки nodriver Tab или Playwright Page.

    Returns:
        Словарь с параметрами виджета ('found', 'solved', 'x', 'y', 'width', 'height', 'interactive')
        либо None, если Turnstile не найден.
    """
    try:
        raw_res = await _evaluate_js(tab, TURNSTILE_INSPECT_JS)
        if isinstance(raw_res, dict) and raw_res.get("found"):
            if (
                raw_res.get("width", 0) < 20 or raw_res.get("height", 0) < 20
            ) and not raw_res.get("solved"):
                cdp_res = await _detect_cf_turnstile_cdp_fallback(tab)
                if cdp_res:
                    return cdp_res
            return raw_res
    except Exception as exc:
        logger.debug(f"Ошибка при инспекции Turnstile: {exc}")

    try:
        return await _detect_cf_turnstile_cdp_fallback(tab)
    except Exception:
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
        if (
            info
            and not clicked
            and info.get("visible")
            and info.get("interactive", True)
        ):
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
