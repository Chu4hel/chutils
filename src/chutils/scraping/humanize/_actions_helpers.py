"""Вспомогательные утилиты, проверки зависимостей и маппинги клавиш для humanize actions."""

from __future__ import annotations

import importlib.util
import random
import sys
from typing import Any

from chutils.exceptions import OptionalDependencyError


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


