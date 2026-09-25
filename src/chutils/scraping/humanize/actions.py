import asyncio
import random
import time
from typing import Any

from ._actions_helpers import (
    _async_type_nodriver,
    _async_type_playwright,
    _build_selenium_key_map,
    _ensure_nodriver,
    _ensure_playwright,
    _ensure_selenium,
    _generate_scroll_points,
    _is_nodriver,
    _is_playwright,
    _resolve_async_element_coordinates,
    _run_with_timeout,
    _safe_get_async_url,
    async_human_sleep,
    click,
    human_sleep,
)
from .math_utils import (
    BezierCurveGenerator,
    JitterDelayGenerator,
    KeyboardTypoGenerator,
    WindMouseGenerator,
)

__all__ = [
    "_build_selenium_key_map",
    "_ensure_nodriver",
    "_ensure_playwright",
    "_ensure_selenium",
    "_generate_scroll_points",
    "_is_nodriver",
    "_is_playwright",
    "_safe_get_async_url",
    "async_click",
    "async_human_sleep",
    "async_move_mouse",
    "async_scroll_to",
    "async_type_text",
    "click",
    "human_sleep",
    "move_mouse",
    "scroll_to",
    "type_text",
]


async def async_move_mouse(
    page: Any,
    x: int,
    y: int,
    start: tuple[int, int] | None = None,
    steps: int = 30,
    delay_between_steps: float = 0.01,
    algorithm: str = "bezier",
    *,
    timeout: float | None = None,
) -> None:
    """Имитирует плавное перемещение мыши Playwright или nodriver.

    Args:
        page: Объект страницы Playwright Page или вкладки nodriver Tab.
        x: Конечная координата X.
        y: Конечная координата Y.
        start: Начальные координаты X, Y. Если не задано, используется (0, 0).
        steps: Количество промежуточных шагов движения (для алгоритма 'bezier').
        delay_between_steps: Задержка между шагами в секундах (для алгоритма 'bezier').
        algorithm: Алгоритм генерации траектории ('bezier' или 'windmouse').
        timeout: Максимальное время ожидания операции (в секундах).
    """
    async def _move() -> None:
        start_pt = start or (0, 0)
        algo = algorithm.lower().replace("_", "").replace("-", "")
        if algo == "windmouse":
            wind_gen = WindMouseGenerator()
            points_with_delay = wind_gen.generate(start_pt, (x, y))

            if _is_nodriver(page):
                _ensure_nodriver()
                from nodriver.cdp import input_ as cdp_input

                for px, py, step_delay in points_with_delay:
                    await page.send(
                        cdp_input.dispatch_mouse_event(
                            type_="mouseMoved",
                            x=px,
                            y=py,
                        )
                    )
                    if step_delay > 0:
                        await asyncio.sleep(step_delay)
            elif _is_playwright(page):
                _ensure_playwright()

                for px, py, step_delay in points_with_delay:
                    await page.mouse.move(px, py)
                    if step_delay > 0:
                        await asyncio.sleep(step_delay)
            else:
                raise ValueError(
                    f"Не удалось определить тип переданного объекта: {type(page)}. "
                    "Убедитесь, что передан объект Playwright (Page) или nodriver (Tab/Element)."
                )
            return

        if _is_nodriver(page):
            _ensure_nodriver()
            from nodriver.cdp import input_ as cdp_input

            curve_gen = BezierCurveGenerator()
            points = curve_gen.generate(start_pt, (x, y), steps=steps)

            for px, py in points:
                await page.send(
                    cdp_input.dispatch_mouse_event(
                        type_="mouseMoved",
                        x=px,
                        y=py,
                    )
                )
                if delay_between_steps > 0:
                    await asyncio.sleep(delay_between_steps)
        elif _is_playwright(page):
            _ensure_playwright()

            curve_gen = BezierCurveGenerator()
            points = curve_gen.generate(start_pt, (x, y), steps=steps)

            for px, py in points:
                await page.mouse.move(px, py)
                if delay_between_steps > 0:
                    await asyncio.sleep(delay_between_steps)
        else:
            raise ValueError(
                f"Не удалось определить тип переданного объекта: {type(page)}. "
                "Убедитесь, что передан объект Playwright (Page) или nodriver (Tab/Element)."
            )

    await _run_with_timeout(_move(), timeout)


async def async_scroll_to(
    page: Any,
    x: int,
    y: int,
    selector: str | None = None,
    steps: int = 10,
    delay_between_steps: float = 0.01,
    *,
    timeout: float | None = None,
) -> None:
    """Имитирует плавный скроллинг Playwright или nodriver.

    Args:
        page: Объект страницы Playwright Page или вкладки nodriver Tab.
        x: Конечная горизонтальная позиция скролла.
        y: Конечная вертикальная позиция скролла.
        selector: Необязательный селектор элемента для скролла.
        steps: Количество промежуточных шагов.
        delay_between_steps: Задержка между шагами в секундах.
        timeout: Максимальное время ожидания операции (в секундах).
    """
    async def _scroll() -> None:
        if _is_nodriver(page):
            _ensure_nodriver()

            scroll_x_val = await page.evaluate("window.scrollX || window.pageXOffset || 0")
            scroll_y_val = await page.evaluate("window.scrollY || window.pageYOffset || 0")

            try:
                scroll_x = int(scroll_x_val)
            except (ValueError, TypeError):
                scroll_x = 0
            try:
                scroll_y = int(scroll_y_val)
            except (ValueError, TypeError):
                scroll_y = 0

            points = _generate_scroll_points(scroll_x, scroll_y, x, y, steps)
            for px, py in points:
                await page.evaluate(f"window.scrollTo({px}, {py})")
                if delay_between_steps > 0:
                    await asyncio.sleep(delay_between_steps)

        elif _is_playwright(page):
            _ensure_playwright()

            scroll_x = await page.evaluate("window.scrollX || window.pageXOffset || 0")
            scroll_y = await page.evaluate("window.scrollY || window.pageYOffset || 0")

            points = _generate_scroll_points(scroll_x, scroll_y, x, y, steps)
            for px, py in points:
                await page.evaluate(f"window.scrollTo({px}, {py})")
                if delay_between_steps > 0:
                    await asyncio.sleep(delay_between_steps)

        else:
            raise ValueError(
                f"Не удалось определить тип переданного объекта: {type(page)}. "
                "Убедитесь, что передан объект Playwright (Page) или nodriver (Tab/Element)."
            )

    await _run_with_timeout(_scroll(), timeout)


async def async_type_text(
    page: Any,
    selector: str,
    text: str,
    error_rate: float = 0.05,
    speed_wpm: float = 40.0,
    key_hold_time: tuple[float, float] = (0.04, 0.09),
    layout_error_rate: float = 0.0,
    delayed_fix_rate: float = 0.0,
    paste_threshold: int | None = None,
    paste_delay_before: tuple[float, float] = (0.4, 1.0),
    paste_delay_after: tuple[float, float] = (0.3, 0.8),
    timeout: float | None = None,
) -> None:
    """Имитирует ввод текста с опечатками Playwright или nodriver.

    Поддерживает адаптивный ввод: если длина текста превышает paste_threshold,
    текст вставляется целиком (имитируя вставку из буфера обмена Ctrl+V / Paste)
    с естественными паузами обдумывания до и после вставки.

    Args:
        page: Объект страницы Playwright Page или вкладки nodriver Tab.
        selector: Селектор поля ввода.
        text: Текст для ввода.
        error_rate: Вероятность совершения опечатки (0.0 - 1.0).
        speed_wpm: Скорость ввода в словах в минуту (WPM).
        key_hold_time: Диапазон задержки удержания клавиши (keyDown -> keyUp) в секундах.
        layout_error_rate: Вероятность ошибки переключения раскладки в начале ввода (0.0 - 1.0).
        delayed_fix_rate: Вероятность отложенного исправления опечатки навигацией стрелками (0.0 - 1.0).
        paste_threshold: Порог длины текста для вставки через буфер обмена. Если None, ввод всегда посимвольный.
        paste_delay_before: Диапазон паузы обдумывания перед вставкой из буфера (в секундах).
        paste_delay_after: Диапазон паузы проверки после вставки из буфера (в секундах).
        timeout: Таймаут выполнения операции в секундах.
    """
    async def _type() -> None:
        delay_gen = JitterDelayGenerator(strategy="lognormal", jitter=0.25)
        typo_gen = KeyboardTypoGenerator()

        if _is_nodriver(page):
            await _async_type_nodriver(
                page,
                selector,
                text,
                error_rate=error_rate,
                speed_wpm=speed_wpm,
                key_hold_time=key_hold_time,
                layout_error_rate=layout_error_rate,
                delayed_fix_rate=delayed_fix_rate,
                paste_threshold=paste_threshold,
                paste_delay_before=paste_delay_before,
                paste_delay_after=paste_delay_after,
                delay_gen=delay_gen,
                typo_gen=typo_gen,
            )
        elif _is_playwright(page):
            await _async_type_playwright(
                page,
                selector,
                text,
                error_rate=error_rate,
                speed_wpm=speed_wpm,
                layout_error_rate=layout_error_rate,
                delayed_fix_rate=delayed_fix_rate,
                paste_threshold=paste_threshold,
                paste_delay_before=paste_delay_before,
                paste_delay_after=paste_delay_after,
                delay_gen=delay_gen,
                typo_gen=typo_gen,
            )
        else:
            raise ValueError(
                f"Не удалось определить тип переданного объекта: {type(page)}. "
                "Убедитесь, что передан объект Playwright (Page) или nodriver (Tab/Element)."
            )

    await _run_with_timeout(_type(), timeout)



def move_mouse(
    driver: Any,
    x: int,
    y: int,
    start: tuple[int, int] | None = None,
    steps: int = 30,
    delay_between_steps: float = 0.01,
    algorithm: str = "bezier",
) -> None:
    """Имитирует плавное перемещение мыши Selenium.

    Args:
        driver: Экземпляр Selenium WebDriver.
        x: Конечная координата X.
        y: Конечная координата Y.
        start: Начальные координаты X, Y. Если не задано, используется (0, 0).
        steps: Количество промежуточных шагов (для алгоритма 'bezier').
        delay_between_steps: Задержка между шагами в секундах (для алгоритма 'bezier').
        algorithm: Алгоритм генерации траектории ('bezier' или 'windmouse').
    """
    _ensure_selenium()
    from selenium.webdriver.common.action_chains import ActionChains

    start_pt = start or (0, 0)
    algo = algorithm.lower().replace("_", "").replace("-", "")

    if algo == "windmouse":
        wind_gen = WindMouseGenerator()
        points = wind_gen.generate(start_pt, (x, y))

        prev_x, prev_y = start_pt
        for px, py, step_delay in points:
            dx = px - prev_x
            dy = py - prev_y
            ActionChains(driver).move_by_offset(dx, dy).perform()
            prev_x, prev_y = px, py
            if step_delay > 0:
                time.sleep(step_delay)
        return

    curve_gen = BezierCurveGenerator()
    points_bezier = curve_gen.generate(start_pt, (x, y), steps=steps)

    prev_x, prev_y = start_pt
    for px, py in points_bezier:
        dx = px - prev_x
        dy = py - prev_y
        ActionChains(driver).move_by_offset(dx, dy).perform()
        prev_x, prev_y = px, py
        if delay_between_steps > 0:
            time.sleep(delay_between_steps)


def scroll_to(
    driver: Any,
    x: int,
    y: int,
    selector: str | None = None,
    steps: int = 10,
    delay_between_steps: float = 0.01,
) -> None:
    """Имитирует плавный скроллинг Selenium.

    Args:
        driver: Экземпляр Selenium WebDriver.
        x: Конечная горизонтальная позиция скролла.
        y: Конечная вертикальная позиция скролла.
        selector: Необязательный селектор элемента для скролла.
        steps: Количество промежуточных шагов.
        delay_between_steps: Задержка между шагами в секундах.
    """
    _ensure_selenium()

    scroll_x = driver.execute_script(
        "return window.scrollX || window.pageXOffset || 0;"
    )
    scroll_y = driver.execute_script(
        "return window.scrollY || window.pageYOffset || 0;"
    )

    points = _generate_scroll_points(scroll_x, scroll_y, x, y, steps)
    for px, py in points:
        driver.execute_script(f"window.scrollTo({px}, {py});")
        if delay_between_steps > 0:
            time.sleep(delay_between_steps)


def type_text(
    driver: Any,
    selector: str,
    text: str,
    error_rate: float = 0.05,
    speed_wpm: float = 40.0,
    layout_error_rate: float = 0.0,
    delayed_fix_rate: float = 0.0,
    paste_threshold: int | None = None,
    paste_delay_before: tuple[float, float] = (0.4, 1.0),
    paste_delay_after: tuple[float, float] = (0.3, 0.8),
) -> None:
    """Имитирует ввод текста с опечатками Selenium.

    Поддерживает адаптивный ввод: если длина текста превышает paste_threshold,
    текст вставляется целиком (Ctrl+V / Paste) с естественными паузами обдумывания.

    Args:
        driver: Экземпляр Selenium WebDriver.
        selector: CSS-селектор поля ввода.
        text: Текст для ввода.
        error_rate: Вероятность совершения опечатки (0.0 - 1.0).
        speed_wpm: Скорость ввода в словах в минуту (WPM).
        layout_error_rate: Вероятность ошибки переключения раскладки в начале ввода (0.0 - 1.0).
        delayed_fix_rate: Вероятность отложенного исправления опечатки навигацией стрелками (0.0 - 1.0).
        paste_threshold: Порог длины текста для вставки через буфер обмена. Если None, ввод всегда посимвольный.
        paste_delay_before: Диапазон паузы обдумывания перед вставкой из буфера (в секундах).
        paste_delay_after: Диапазон паузы проверки после вставки из буфера (в секундах).
    """
    _ensure_selenium()
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys

    element = driver.find_element(By.CSS_SELECTOR, selector)
    element.click()

    # Адаптивная вставка длинного текста через буфер обмена
    if paste_threshold is not None and len(text) >= paste_threshold:
        delay_before = (
            random.uniform(*paste_delay_before)
            if paste_delay_before and paste_delay_before[1] > 0
            else 0.0
        )
        if delay_before > 0:
            time.sleep(delay_before)

        driver.execute_script(
            "arguments[0].focus(); document.execCommand('insertText', false, arguments[1]);",
            element,
            text,
        )

        delay_after = (
            random.uniform(*paste_delay_after)
            if paste_delay_after and paste_delay_after[1] > 0
            else 0.0
        )
        if delay_after > 0:
            time.sleep(delay_after)
        return

    char_delay = 60.0 / (speed_wpm * 5)
    delay_gen = JitterDelayGenerator(strategy="lognormal", jitter=0.25)
    typo_gen = KeyboardTypoGenerator()
    sequence = typo_gen.generate_sequence(
        text,
        error_rate=error_rate,
        layout_error_rate=layout_error_rate,
        delayed_fix_rate=delayed_fix_rate,
    )

    selenium_keys_map = _build_selenium_key_map(Keys)

    for action in sequence:
        if action.action == "type":
            element.send_keys(action.char)
        elif action.action == "backspace":
            element.send_keys(Keys.BACKSPACE)
        elif action.action == "key":
            element.send_keys(selenium_keys_map.get(action.char, action.char))

        delay = delay_gen.generate(char_delay)
        if delay > 0:
            time.sleep(delay)


async def async_click(
    page: Any,
    selector: str | None = None,
    x: int | None = None,
    y: int | None = None,
    start: tuple[int, int] | None = None,
    algorithm: str = "windmouse",
    button: str = "left",
    hold_time: tuple[float, float] = (0.05, 0.12),
    timeout: float | None = None,
) -> None:
    """Имитирует реалистичный клик мышью (с плавным наведением, микропаузами и удержанием кнопки).

    Args:
        page: Объект страницы Playwright Page или вкладки nodriver Tab.
        selector: Селектор целевого элемента (если x, y не заданы).
        x: Конечная координата X.
        y: Конечная координата Y.
        start: Начальные координаты курсора.
        algorithm: Алгоритм движения ('windmouse' или 'bezier').
        button: Кнопка мыши ('left', 'right', 'middle').
        hold_time: Диапазон задержки удержания кнопки мыши (в секундах).
        timeout: Таймаут выполнения операции в секундах.
    """
    async def _click() -> None:
        target_x = x
        target_y = y

        if target_x is None or target_y is None:
            if selector is None:
                raise ValueError(
                    "Необходимо указать координаты (x, y) или CSS-селектор selector."
                )

            target_x, target_y = await _resolve_async_element_coordinates(page, selector)

        # 1. Плавное перемещение к цели
        await async_move_mouse(
            page, x=target_x, y=target_y, start=start, algorithm=algorithm
        )

        # 2. Пауза перед нажатием
        await asyncio.sleep(random.uniform(0.04, 0.12))

        # 3. Нажатие, удержание и отпускание кнопки
        hold_delay = (
            random.uniform(*hold_time)
            if hold_time and hold_time[1] > 0
            else random.uniform(0.04, 0.09)
        )
        if _is_nodriver(page):
            _ensure_nodriver()
            from nodriver.cdp import input_ as cdp_input

            btn = (
                "left" if button == "left" else ("right" if button == "right" else "middle")
            )
            await page.send(
                cdp_input.dispatch_mouse_event(
                    type_="mousePressed",
                    x=target_x,
                    y=target_y,
                    button=cdp_input.MouseButton(btn),
                    click_count=1,
                )
            )
            await asyncio.sleep(hold_delay)
            await page.send(
                cdp_input.dispatch_mouse_event(
                    type_="mouseReleased",
                    x=target_x,
                    y=target_y,
                    button=cdp_input.MouseButton(btn),
                    click_count=1,
                )
            )
        elif _is_playwright(page):
            _ensure_playwright()
            await page.mouse.down(button=button)
            await asyncio.sleep(hold_delay)
            await page.mouse.up(button=button)

        # 4. Пауза после клика
        await asyncio.sleep(random.uniform(0.03, 0.08))

    await _run_with_timeout(_click(), timeout)

