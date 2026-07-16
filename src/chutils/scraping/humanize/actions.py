import asyncio
import importlib.util
import random
import time
from typing import Any

from chutils.exceptions import OptionalDependencyError
from .math_utils import BezierCurveGenerator, JitterDelayGenerator, KeyboardTypoGenerator


# Ленивая проверка наличия библиотек
def _ensure_playwright() -> None:
    if importlib.util.find_spec("playwright") is None:
        raise OptionalDependencyError(
            "Модуль 'playwright' не установлен. Для использования Playwright-интеграций "
            "установите его: pip install chutils[scraping] или pip install playwright.",
            dependency="playwright",
            hint="Выполните pip install chutils[scraping] или pip install playwright."
        )


def _ensure_selenium() -> None:
    if importlib.util.find_spec("selenium") is None:
        raise OptionalDependencyError(
            "Модуль 'selenium' не установлен. Для использования Selenium-интеграций "
            "установите его: pip install chutils[scraping] или pip install selenium.",
            dependency="selenium",
            hint="Выполните pip install chutils[scraping] или pip install selenium."
        )


def _get_lognormal_delay(min_seconds: float, max_seconds: float) -> float:
    """Генерирует логнормальное случайное время в заданном интервале."""
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
    delay = _get_lognormal_delay(min_seconds, max_seconds)
    time.sleep(delay)


async def async_human_sleep(min_seconds: float, max_seconds: float) -> None:
    """Асинхронно задерживает выполнение на случайное время, имитируя поведение человека.

    Args:
        min_seconds: Минимальное время задержки (в секундах).
        max_seconds: Максимальное время задержки (в секундах).
    """
    delay = _get_lognormal_delay(min_seconds, max_seconds)
    await asyncio.sleep(delay)


async def async_move_mouse(
        page: Any,
        x: int,
        y: int,
        start: tuple[int, int] | None = None,
        steps: int = 30,
        delay_between_steps: float = 0.01,
) -> None:
    """Имитирует плавное перемещение мыши Playwright.

    Args:
        page: Объект страницы Playwright Page.
        x: Конечная координата X.
        y: Конечная координата Y.
        start: Начальные координаты X, Y. Если не задано, используется (0, 0).
        steps: Количество промежуточных шагов движения.
        delay_between_steps: Задержка между шагами в секундах.
    """
    _ensure_playwright()

    start_pt = start or (0, 0)
    curve_gen = BezierCurveGenerator()
    points = curve_gen.generate(start_pt, (x, y), steps=steps)

    for px, py in points:
        await page.mouse.move(px, py)
        if delay_between_steps > 0:
            await asyncio.sleep(delay_between_steps)


async def async_scroll_to(
        page: Any,
        x: int,
        y: int,
        selector: str | None = None,
        steps: int = 10,
        delay_between_steps: float = 0.01,
) -> None:
    """Имитирует плавный скроллинг Playwright.

    Args:
        page: Объект страницы Playwright Page.
        x: Конечная горизонтальная позиция скролла.
        y: Конечная вертикальная позиция скролла.
        selector: Необязательный селектор элемента для скролла.
        steps: Количество промежуточных шагов.
        delay_between_steps: Задержка между шагами в секундах.
    """
    _ensure_playwright()

    scroll_x = await page.evaluate("window.scrollX || window.pageXOffset || 0")
    scroll_y = await page.evaluate("window.scrollY || window.pageYOffset || 0")

    points = []
    for i in range(steps):
        t = (i + 1) / steps
        px = int(scroll_x + (x - scroll_x) * t)
        py = int(scroll_y + (y - scroll_y) * t)
        points.append((px, py))

    for px, py in points:
        await page.evaluate(f"window.scrollTo({px}, {py})")
        if delay_between_steps > 0:
            await asyncio.sleep(delay_between_steps)


async def async_type_text(
        page: Any, selector: str, text: str, error_rate: float = 0.05, speed_wpm: float = 40.0
) -> None:
    """Имитирует ввод текста с опечатками Playwright.

    Args:
        page: Объект страницы Playwright Page.
        selector: Селектор поля ввода.
        text: Текст для ввода.
        error_rate: Вероятность совершения опечатки (0.0 - 1.0).
        speed_wpm: Скорость ввода в словах в минуту (WPM).
    """
    _ensure_playwright()
    await page.focus(selector)

    # 40 WPM = 200 CPM (символов в минуту) = 0.3 секунды на символ
    char_delay = 60.0 / (speed_wpm * 5)
    delay_gen = JitterDelayGenerator(strategy="lognormal", jitter=0.25)
    typo_gen = KeyboardTypoGenerator()
    sequence = typo_gen.generate_sequence(text, error_rate)

    for action in sequence:
        if action.action == "type":
            await page.keyboard.type(action.char)
        elif action.action == "backspace":
            await page.keyboard.press("Backspace")

        delay = delay_gen.generate(char_delay)
        if delay > 0:
            await asyncio.sleep(delay)


def move_mouse(
        driver: Any,
        x: int,
        y: int,
        start: tuple[int, int] | None = None,
        steps: int = 30,
        delay_between_steps: float = 0.01,
) -> None:
    """Имитирует плавное перемещение мыши Selenium.

    Args:
        driver: Экземпляр Selenium WebDriver.
        x: Конечная координата X.
        y: Конечная координата Y.
        start: Начальные координаты X, Y. Если не задано, используется (0, 0).
        steps: Количество промежуточных шагов.
        delay_between_steps: Задержка между шагами в секундах.
    """
    _ensure_selenium()
    from selenium.webdriver.common.action_chains import ActionChains

    start_pt = start or (0, 0)
    curve_gen = BezierCurveGenerator()
    points = curve_gen.generate(start_pt, (x, y), steps=steps)

    prev_x, prev_y = start_pt
    for px, py in points:
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

    scroll_x = driver.execute_script("return window.scrollX || window.pageXOffset || 0;")
    scroll_y = driver.execute_script("return window.scrollY || window.pageYOffset || 0;")

    points = []
    for i in range(steps):
        t = (i + 1) / steps
        px = int(scroll_x + (x - scroll_x) * t)
        py = int(scroll_y + (y - scroll_y) * t)
        points.append((px, py))

    for px, py in points:
        driver.execute_script(f"window.scrollTo({px}, {py});")
        if delay_between_steps > 0:
            time.sleep(delay_between_steps)


def type_text(
        driver: Any, selector: str, text: str, error_rate: float = 0.05, speed_wpm: float = 40.0
) -> None:
    """Имитирует ввод текста с опечатками Selenium.

    Args:
        driver: Экземпляр Selenium WebDriver.
        selector: CSS-селектор поля ввода.
        text: Текст для ввода.
        error_rate: Вероятность совершения опечатки (0.0 - 1.0).
        speed_wpm: Скорость ввода в словах в минуту (WPM).
    """
    _ensure_selenium()
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys

    element = driver.find_element(By.CSS_SELECTOR, selector)
    element.click()

    char_delay = 60.0 / (speed_wpm * 5)
    delay_gen = JitterDelayGenerator(strategy="lognormal", jitter=0.25)
    typo_gen = KeyboardTypoGenerator()
    sequence = typo_gen.generate_sequence(text, error_rate)

    for action in sequence:
        if action.action == "type":
            element.send_keys(action.char)
        elif action.action == "backspace":
            element.send_keys(Keys.BACKSPACE)

        delay = delay_gen.generate(char_delay)
        if delay > 0:
            time.sleep(delay)
