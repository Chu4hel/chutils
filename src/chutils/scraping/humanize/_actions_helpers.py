"""Вспомогательные утилиты, проверки зависимостей и маппинги клавиш для humanize actions."""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
import importlib.util
import json
import random
import sys
import time
from typing import Any

from chutils.exceptions import OptionalDependencyError


async def _run_with_timeout(
    coro: Coroutine[Any, Any, Any],
    timeout: float | None = None,
) -> Any:
    """Выполняет корутину с опциональным ограничением по таймауту.

    Args:
        coro: Асинхронная корутина.
        timeout: Таймаут в секундах. Если None, выполняется без таймаута.

    Returns:
        Результат выполнения корутины.
    """
    if timeout is not None:
        return await asyncio.wait_for(coro, timeout=timeout)
    return await coro


def _ensure_playwright() -> None:
    """Проверяет доступность библиотеки playwright."""
    if "playwright" in sys.modules:
        return
    try:
        if importlib.util.find_spec("playwright") is None:
            raise ImportError()
    except (ImportError, ValueError):
        raise OptionalDependencyError(
            "Модуль 'playwright' не установлен. Для использования Playwright-интеграций "
            "установите его: pip install chutils[scraping] или pip install playwright.",
            dependency="playwright",
            hint="Выполните pip install chutils[scraping] или pip install playwright.",
        )


def _ensure_selenium() -> None:
    """Проверяет доступность библиотеки selenium."""
    if "selenium" in sys.modules:
        return
    try:
        if importlib.util.find_spec("selenium") is None:
            raise ImportError()
    except (ImportError, ValueError):
        raise OptionalDependencyError(
            "Модуль 'selenium' не установлен. Для использования Selenium-интеграций "
            "установите его: pip install chutils[scraping] или pip install selenium.",
            dependency="selenium",
            hint="Выполните pip install chutils[scraping] или pip install selenium.",
        )


def _ensure_nodriver() -> None:
    """Проверяет доступность библиотеки nodriver."""
    if "nodriver" in sys.modules:
        try:
            from unittest.mock import Mock

            is_mock = isinstance(sys.modules["nodriver"], Mock)
        except ImportError:
            is_mock = False
        if not is_mock:
            return
    try:
        if importlib.util.find_spec("nodriver") is None:
            raise ImportError()
    except (ImportError, ValueError):
        raise OptionalDependencyError(
            "Модуль 'nodriver' не установлен. Для использования nodriver-интеграций "
            "установите его в ваше окружение (например, pip install nodriver или uv add nodriver).",
            dependency="nodriver",
            hint="Установите пакет nodriver в ваше окружение (через pip, uv или poetry).",
        )


def _is_nodriver(obj: Any) -> bool:
    """Определяет, является ли переданный объект элементом или вкладкой nodriver."""
    try:
        from unittest.mock import Mock

        is_mock = isinstance(obj, Mock)
    except ImportError:
        is_mock = False

    if is_mock:
        return getattr(obj, "_is_nodriver", False) is True

    return hasattr(obj, "send") and callable(obj.send)


def _is_playwright(obj: Any) -> bool:
    """Определяет, является ли переданный объект страницей Playwright."""
    if obj is None:
        return True
    return not _is_nodriver(obj) and (
        hasattr(obj, "mouse")
        or hasattr(obj, "keyboard")
        or hasattr(obj, "evaluate")
        or hasattr(obj, "focus")
    )


def _get_lognormal_delay(min_seconds: float, max_seconds: float) -> float:
    """Генерирует логнормальное случайное время в заданном интервале.

    Args:
        min_seconds: Минимальное время задержки (в секундах).
        max_seconds: Максимальное время задержки (в секундах).

    Returns:
        Случайное значение задержки с нормальным/логнормальным распределением.
    """
    if min_seconds <= 0:
        return 0.0
    if min_seconds >= max_seconds:
        return min_seconds

    mean = (min_seconds + max_seconds) / 2
    sigma = (max_seconds - min_seconds) / 6.0  # 3-сигма правило
    val = random.gauss(mean, sigma)
    return max(min_seconds, min(val, max_seconds))


def human_sleep(min_seconds: float, max_seconds: float) -> None:
    """Синхронно задерживает выполнение на случайное время, имитируя поведение человека.

    Args:
        min_seconds: Минимальное время задержки (в секундах).
        max_seconds: Максимальное время задержки (в секундах).
    """
    import time

    delay = _get_lognormal_delay(min_seconds, max_seconds)
    time.sleep(delay)


async def async_human_sleep(min_seconds: float, max_seconds: float) -> None:
    """Асинхронно задерживает выполнение на случайное время, имитируя поведение человека.

    Args:
        min_seconds: Минимальное время задержки (в секундах).
        max_seconds: Максимальное время задержки (в секундах).
    """
    import asyncio

    delay = _get_lognormal_delay(min_seconds, max_seconds)
    await asyncio.sleep(delay)


def _build_selenium_key_map(keys_cls: Any) -> dict[str, Any]:
    """Строит маппинг строковых идентификаторов клавиш на константы Selenium Keys.

    Args:
        keys_cls: Класс selenium.webdriver.common.keys.Keys.

    Returns:
        Словарь соответствия символов константам Selenium Keys.
    """
    return {
        "ArrowLeft": getattr(keys_cls, "ARROW_LEFT", "ArrowLeft"),
        "ArrowRight": getattr(keys_cls, "ARROW_RIGHT", "ArrowRight"),
        "End": getattr(keys_cls, "END", "End"),
        "Home": getattr(keys_cls, "HOME", "Home"),
        "Backspace": getattr(keys_cls, "BACKSPACE", "Backspace"),
        "Delete": getattr(keys_cls, "DELETE", "Delete"),
    }


def _generate_scroll_points(
    start_x: int, start_y: int, target_x: int, target_y: int, steps: int
) -> list[tuple[int, int]]:
    """Генерирует промежуточные координаты для плавного скроллинга.

    Args:
        start_x: Текущая координата X.
        start_y: Текущая координата Y.
        target_x: Конечная координата X.
        target_y: Конечная координата Y.
        steps: Количество промежуточных шагов.

    Returns:
        Список пар координат (px, py).
    """
    points: list[tuple[int, int]] = []
    for i in range(steps):
        t = (i + 1) / steps
        px = int(start_x + (target_x - start_x) * t)
        py = int(start_y + (target_y - start_y) * t)
        points.append((px, py))
    return points


async def _resolve_async_element_coordinates(
    page: Any, selector: str
) -> tuple[int, int]:
    """Определяет координаты клика внутри элемента для Playwright или nodriver."""
    if _is_nodriver(page):
        _ensure_nodriver()
        # 1. Сначала пробуем получить точные экранные координаты через JS getBoundingClientRect()
        # Это работает со сложными селекторами, псевдоклассами, запятыми, CDK Overlay и Shadow DOM
        if hasattr(page, "evaluate") and callable(page.evaluate):
            try:
                js_rect = (
                    "(function(sel) {"
                    "  var el = document.querySelector(sel);"
                    "  if (!el) return null;"
                    "  var rect = el.getBoundingClientRect();"
                    "  return {"
                    "    x: rect.left,"
                    "    y: rect.top,"
                    "    width: rect.width,"
                    "    height: rect.height"
                    "  };"
                    "})"
                )
                box_dict = await page.evaluate(f"({js_rect})({json.dumps(selector)})")
                if isinstance(box_dict, dict) and "x" in box_dict and "y" in box_dict:
                    bx = float(box_dict.get("x", 0.0))
                    by = float(box_dict.get("y", 0.0))
                    bw = float(box_dict.get("width", 0.0))
                    bh = float(box_dict.get("height", 0.0))
                    return (
                        int(bx + bw * random.uniform(0.3, 0.7)),
                        int(by + bh * random.uniform(0.3, 0.7)),
                    )
            except Exception:
                pass

        # 2. Fallback: поиск через внутренний page.find() nodriver
        try:
            elem = await page.find(selector)
            box = await elem.get_position() if hasattr(elem, "get_position") else None
            if box:
                return (
                    int(box.x + box.width * random.uniform(0.3, 0.7)),
                    int(box.y + box.height * random.uniform(0.3, 0.7)),
                )
        except Exception:
            pass

        return (100, 100)
    elif _is_playwright(page):
        _ensure_playwright()
        elem = (
            await page.query_selector(selector)
            if hasattr(page, "query_selector")
            else None
        )
        if elem is not None:
            box = await elem.bounding_box()
            if box:
                return (
                    int(box["x"] + box["width"] * random.uniform(0.3, 0.7)),
                    int(box["y"] + box["height"] * random.uniform(0.3, 0.7)),
                )
        return (100, 100)
    else:
        raise ValueError(
            f"Не удалось определить тип переданного объекта: {type(page)}. "
            "Убедитесь, что передан объект Playwright (Page) или nodriver (Tab/Element)."
        )


JS_DOM_PASTE_SCRIPT = (
    "(function(sel, val) {"
    "  var el = document.querySelector(sel);"
    "  if (!el) return false;"
    "  var proto = Object.getPrototypeOf(el);"
    "  var desc = Object.getOwnPropertyDescriptor(proto, 'value') || "
    "             Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value') || "
    "             Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value');"
    "  if (desc && desc.set) {"
    "    desc.set.call(el, val);"
    "  } else if ('value' in el) {"
    "    el.value = val;"
    "  } else {"
    "    el.textContent = val;"
    "  }"
    "  el.dispatchEvent(new Event('input', { bubbles: true }));"
    "  el.dispatchEvent(new Event('change', { bubbles: true }));"
    "  return true;"
    "})"
)


JS_DOM_HEAL_SCRIPT = (
    "(function(sel, expected) {"
    "  var el = document.querySelector(sel);"
    "  if (!el) return;"
    "  var current = el.value !== undefined ? el.value : el.textContent;"
    "  if (current !== expected) {"
    "    var proto = Object.getPrototypeOf(el);"
    "    var desc = Object.getOwnPropertyDescriptor(proto, 'value') || "
    "               Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value') || "
    "               Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value');"
    "    if (desc && desc.set) {"
    "      desc.set.call(el, expected);"
    "    } else if ('value' in el) {"
    "      el.value = expected;"
    "    } else {"
    "      el.textContent = expected;"
    "    }"
    "    el.dispatchEvent(new Event('input', { bubbles: true }));"
    "    el.dispatchEvent(new Event('change', { bubbles: true }));"
    "  }"
    "})"
)


async def _dom_safe_paste(page: Any, selector: str, text: str) -> bool:
    """Безопасно вставляет текст через DOM Prototype Setter с диспатчем input/change.

    Args:
        page: Объект страницы Playwright или вкладки nodriver.
        selector: CSS-селектор целевого элемента.
        text: Вставляемый текст.

    Returns:
        True, если вставка через JS выполнена успешно, иначе False.
    """
    if hasattr(page, "evaluate") and callable(page.evaluate):
        try:
            res = await page.evaluate(
                f"({JS_DOM_PASTE_SCRIPT})({json.dumps(selector)}, {json.dumps(text)})"
            )
            return res is True
        except Exception:
            return False
    return False


async def _dom_safe_heal(page: Any, selector: str, expected_text: str) -> None:
    """Выполняет сверку и самовосстановление значения поля ввода через DOM.

    Args:
        page: Объект страницы Playwright или вкладки nodriver.
        selector: CSS-селектор целевого элемента.
        expected_text: Ожидаемый итоговый текст.
    """
    if hasattr(page, "evaluate") and callable(page.evaluate):
        try:
            await page.evaluate(
                f"({JS_DOM_HEAL_SCRIPT})({json.dumps(selector)}, {json.dumps(expected_text)})"
            )
        except Exception:
            pass


async def _async_type_nodriver(
    page: Any,
    selector: str,
    text: str,
    *,
    error_rate: float,
    speed_wpm: float,
    key_hold_time: tuple[float, float],
    layout_error_rate: float,
    delayed_fix_rate: float,
    paste_threshold: int | None,
    paste_delay_before: tuple[float, float],
    paste_delay_after: tuple[float, float],
    delay_gen: Any,
    typo_gen: Any,
) -> None:
    """Выполняет посимвольный ввод или paste для nodriver."""
    _ensure_nodriver()
    from nodriver.cdp import input_ as cdp_input

    element = await page.find(selector)
    await element.focus()

    if paste_threshold is not None and len(text) >= paste_threshold:
        if paste_delay_before and paste_delay_before[1] > 0:
            await asyncio.sleep(random.uniform(*paste_delay_before))

        pasted = await _dom_safe_paste(page, selector, text)
        if not pasted:
            await page.send(cdp_input.insert_text(text=text))

        if paste_delay_after and paste_delay_after[1] > 0:
            await asyncio.sleep(random.uniform(*paste_delay_after))
        return

    char_delay = 60.0 / (speed_wpm * 5)
    sequence = typo_gen.generate_sequence(
        text,
        error_rate=error_rate,
        layout_error_rate=layout_error_rate,
        delayed_fix_rate=delayed_fix_rate,
    )

    for action in sequence:
        if action.action == "type":
            c = action.char
            await page.send(
                cdp_input.dispatch_key_event(type_="keyDown", text=c, unmodified_text=c, key=c)
            )
            if key_hold_time and key_hold_time[1] > 0:
                await asyncio.sleep(random.uniform(*key_hold_time))
            await page.send(
                cdp_input.dispatch_key_event(type_="keyUp", text=c, unmodified_text=c, key=c)
            )
        elif action.action == "backspace":
            await page.send(
                cdp_input.dispatch_key_event(
                    type_="rawKeyDown",
                    key="Backspace",
                    code="Backspace",
                    windows_virtual_key_code=8,
                    native_virtual_key_code=8,
                    commands=["deleteContentBackward"],
                )
            )
            if key_hold_time and key_hold_time[1] > 0:
                await asyncio.sleep(random.uniform(*key_hold_time))
            await page.send(
                cdp_input.dispatch_key_event(
                    type_="keyUp",
                    key="Backspace",
                    code="Backspace",
                    windows_virtual_key_code=8,
                    native_virtual_key_code=8,
                )
            )
        elif action.action == "key":
            k = action.char
            vk = {
                "ArrowLeft": 37, "ArrowUp": 38, "ArrowRight": 39,
                "ArrowDown": 40, "Backspace": 8, "Enter": 13,
            }.get(k, 0)
            extra: dict[str, Any] = {"commands": ["deleteContentBackward"]} if k == "Backspace" else {}
            await page.send(
                cdp_input.dispatch_key_event(
                    type_="rawKeyDown", key=k, code=k,
                    windows_virtual_key_code=vk, native_virtual_key_code=vk, **extra
                )
            )
            if key_hold_time and key_hold_time[1] > 0:
                await asyncio.sleep(random.uniform(*key_hold_time))
            await page.send(
                cdp_input.dispatch_key_event(
                    type_="keyUp", key=k, code=k,
                    windows_virtual_key_code=vk, native_virtual_key_code=vk
                )
            )

        delay = delay_gen.generate(char_delay)
        if delay > 0:
            await asyncio.sleep(delay)

    await _dom_safe_heal(page, selector, text)


async def _async_type_playwright(
    page: Any,
    selector: str,
    text: str,
    *,
    error_rate: float,
    speed_wpm: float,
    layout_error_rate: float,
    delayed_fix_rate: float,
    paste_threshold: int | None,
    paste_delay_before: tuple[float, float],
    paste_delay_after: tuple[float, float],
    delay_gen: Any,
    typo_gen: Any,
) -> None:
    """Выполняет посимвольный ввод или paste для Playwright."""
    _ensure_playwright()
    await page.focus(selector)

    if paste_threshold is not None and len(text) >= paste_threshold:
        if paste_delay_before and paste_delay_before[1] > 0:
            await asyncio.sleep(random.uniform(*paste_delay_before))

        await page.keyboard.insert_text(text)

        if paste_delay_after and paste_delay_after[1] > 0:
            await asyncio.sleep(random.uniform(*paste_delay_after))
        return

    char_delay = 60.0 / (speed_wpm * 5)
    sequence = typo_gen.generate_sequence(
        text,
        error_rate=error_rate,
        layout_error_rate=layout_error_rate,
        delayed_fix_rate=delayed_fix_rate,
    )

    for action in sequence:
        if action.action == "type":
            await page.keyboard.type(action.char)
        elif action.action == "backspace":
            await page.keyboard.press("Backspace")
        elif action.action == "key":
            await page.keyboard.press(action.char)

        delay = delay_gen.generate(char_delay)
        if delay > 0:
            await asyncio.sleep(delay)

    await _dom_safe_heal(page, selector, text)



def click(
    driver: Any,
    selector: str | None = None,
    x: int | None = None,
    y: int | None = None,
    start: tuple[int, int] | None = None,
    algorithm: str = "windmouse",
    hold_time: tuple[float, float] = (0.05, 0.12),
) -> None:
    """Имитирует реалистичный клик мышью Selenium.

    Args:
        driver: Экземпляр Selenium WebDriver.
        selector: CSS-селектор целевого элемента (если x, y не заданы).
        x: Конечная координата X.
        y: Конечная координата Y.
        start: Начальные координаты курсора.
        algorithm: Алгоритм движения ('windmouse' или 'bezier').
        hold_time: Диапазон задержки удержания кнопки мыши (в секундах).
    """
    _ensure_selenium()
    from selenium.webdriver.common.action_chains import ActionChains
    from selenium.webdriver.common.by import By

    from .actions import move_mouse

    target_x = x
    target_y = y

    if target_x is None or target_y is None:
        if selector is None:
            raise ValueError(
                "Необходимо указать координаты (x, y) или CSS-селектор selector."
            )
        element = driver.find_element(By.CSS_SELECTOR, selector)
        loc = element.location
        size = element.size
        target_x = int(loc["x"] + size["width"] * random.uniform(0.3, 0.7))
        target_y = int(loc["y"] + size["height"] * random.uniform(0.3, 0.7))

    move_mouse(driver, x=target_x, y=target_y, start=start, algorithm=algorithm)
    time.sleep(random.uniform(0.04, 0.12))

    hold_delay = (
        random.uniform(*hold_time)
        if hold_time and hold_time[1] > 0
        else random.uniform(0.04, 0.09)
    )
    actions = ActionChains(driver)
    actions.click_and_hold().pause(hold_delay).release().perform()
    time.sleep(random.uniform(0.03, 0.08))
