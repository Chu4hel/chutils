"""Сенсорные взаимодействия, генератор жестов и эмуляция тач-событий."""

from __future__ import annotations

import asyncio
import math
import random
from dataclasses import dataclass
from typing import Any

from ._actions_helpers import (
    _ensure_nodriver,
    _is_nodriver,
    _is_playwright,
    _run_with_timeout,
)
from .math_utils import BezierCurveGenerator

__all__ = [
    "TouchGestureGenerator",
    "TouchPoint",
    "async_touch_swipe",
    "async_touch_tap",
]


@dataclass(slots=True)
class TouchPoint:
    """Точка сенсорного касания с физическими параметрами пятна контакта.

    Attributes:
        x: Координата X на экране.
        y: Координата Y на экране.
        radius_x: Радиус эллипса касания по оси X (в пикселях).
        radius_y: Радиус эллипса касания по оси Y (в пикселях).
        rotation_angle: Угол поворота эллипса касания в градусах.
        force: Сила нажатия (давление) пальца в диапазоне 0.0 - 1.0.
        delay: Задержка перед переходом к следующей точке (в секундах).
    """

    x: float
    y: float
    radius_x: float = 12.0
    radius_y: float = 12.0
    rotation_angle: float = 0.0
    force: float = 0.7
    delay: float = 0.01


class TouchGestureGenerator:
    """Генератор биомеханических сенсорных траекторий (касания, свайпы, зум)."""

    def __init__(
        self,
        *,
        default_radius: float = 12.0,
        default_force: float = 0.7,
        jitter: float = 0.1,
    ) -> None:
        """Инициализирует генератор сенсорных жестов.

        Args:
            default_radius: Базовый радиус пятна касания пальца (в пикселях).
            default_force: Базовая сила нажатия (0.0 - 1.0).
            jitter: Амплитуда случайных микроколебаний.
        """
        self.default_radius = default_radius
        self.default_force = default_force
        self.jitter = jitter

    def generate_tap(
        self,
        x: float,
        y: float,
        *,
        hold_time: float = 0.08,
    ) -> list[TouchPoint]:
        """Генерирует последовательность точек для одиночного касания (tap).

        Args:
            x: Координата X касания.
            y: Координата Y касания.
            hold_time: Время удержания пальца на экране в секундах.

        Returns:
            Список точек TouchPoint (касание и микросдвиг).
        """
        rx = self.default_radius + random.uniform(-1.0, 1.0) * self.jitter * self.default_radius
        ry = self.default_radius + random.uniform(-1.0, 1.0) * self.jitter * self.default_radius
        f = max(0.1, min(1.0, self.default_force + random.uniform(-0.05, 0.05)))

        # Начальная точка касания (touchstart)
        p1 = TouchPoint(
            x=x,
            y=y,
            radius_x=rx,
            radius_y=ry,
            force=f * 0.8,
            delay=hold_time * 0.5,
        )
        # Микросдвиг во время удержания пальца (finger tremor)
        jitter_x = random.uniform(-1.5, 1.5) * self.jitter
        jitter_y = random.uniform(-1.5, 1.5) * self.jitter
        p2 = TouchPoint(
            x=x + jitter_x,
            y=y + jitter_y,
            radius_x=rx * 1.05,
            radius_y=ry * 1.05,
            force=f,
            delay=hold_time * 0.5,
        )
        return [p1, p2]

    def generate_swipe(
        self,
        start: tuple[float, float],
        end: tuple[float, float],
        *,
        steps: int = 25,
        curve: str = "bezier",
    ) -> list[TouchPoint]:
        """Генерирует траекторию свайпа пальцем с реалистичной физикой нажима и пятна контакта.

        Args:
            start: Начальные координаты (X, Y).
            end: Конечные координаты (X, Y).
            steps: Количество промежуточных точек.
            curve: Алгоритм генерации траектории ('bezier').

        Returns:
            Список точек TouchPoint вдоль пути свайпа.
        """
        steps = max(3, steps)
        bezier = BezierCurveGenerator()
        raw_points = bezier.generate(
            (int(start[0]), int(start[1])),
            (int(end[0]), int(end[1])),
            steps=steps,
        )

        result: list[TouchPoint] = []
        for i, (px, py) in enumerate(raw_points):
            t = i / float(steps - 1)
            # Сила нажатия: нарастает от 0.4 до 0.8-0.9 в середине и спадает к концу
            force_bell = math.sin(math.pi * t)
            force = max(
                0.2,
                min(
                    1.0,
                    0.3 + 0.55 * force_bell + random.uniform(-0.03, 0.03) * self.jitter,
                ),
            )

            # Радиус пятна контакта пропорционален силе нажатия
            r_scale = 0.8 + 0.4 * force_bell
            rx = self.default_radius * r_scale + random.uniform(-0.5, 0.5)
            ry = self.default_radius * r_scale * 1.1 + random.uniform(-0.5, 0.5)

            step_delay = 0.008 + 0.006 * (1.0 - force_bell)

            result.append(
                TouchPoint(
                    x=float(px),
                    y=float(py),
                    radius_x=rx,
                    radius_y=ry,
                    force=force,
                    delay=step_delay,
                )
            )
        return result

    def generate_pinch(
        self,
        center: tuple[float, float],
        start_distance: float,
        end_distance: float,
        *,
        steps: int = 20,
        angle: float = 0.0,
    ) -> list[tuple[TouchPoint, TouchPoint]]:
        """Генерирует двухпальцевый жест сжатия / масштабирования (pinch/zoom).

        Args:
            center: Координаты центра жеста (X, Y).
            start_distance: Начальное расстояние между пальцами.
            end_distance: Конечное расстояние между пальцами.
            steps: Количество промежуточных фаз.
            angle: Угол наклона оси жеста в радианах.

        Returns:
            Список пар TouchPoint (finger1, finger2) для каждого шага.
        """
        steps = max(2, steps)
        cx, cy = center
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)

        result: list[tuple[TouchPoint, TouchPoint]] = []
        for i in range(steps):
            t = i / float(steps - 1)
            smooth_t = t * t * (3.0 - 2.0 * t)
            current_dist = start_distance + (end_distance - start_distance) * smooth_t
            half_dist = current_dist / 2.0

            # Палец 1
            f1_x = cx - half_dist * cos_a + random.uniform(-1.0, 1.0) * self.jitter
            f1_y = cy - half_dist * sin_a + random.uniform(-1.0, 1.0) * self.jitter
            # Палец 2
            f2_x = cx + half_dist * cos_a + random.uniform(-1.0, 1.0) * self.jitter
            f2_y = cy + half_dist * sin_a + random.uniform(-1.0, 1.0) * self.jitter

            force = 0.6 + 0.2 * math.sin(math.pi * t)
            rx = self.default_radius * 1.0
            ry = self.default_radius * 1.1

            p1 = TouchPoint(
                x=f1_x, y=f1_y, radius_x=rx, radius_y=ry, force=force, delay=0.01
            )
            p2 = TouchPoint(
                x=f2_x, y=f2_y, radius_x=rx, radius_y=ry, force=force, delay=0.01
            )
            result.append((p1, p2))

        return result


async def async_touch_tap(
    page: Any,
    x: float,
    y: float,
    *,
    hold_time: float = 0.08,
    timeout: float | None = None,
) -> None:
    """Имитирует сенсорное касание (tap) на мобильном экране в Playwright или nodriver.

    Args:
        page: Объект страницы Playwright Page или вкладки nodriver Tab.
        x: Координата X касания.
        y: Координата Y касания.
        hold_time: Время удержания пальца (в секундах).
        timeout: Таймаут выполнения операции (в секундах).
    """

    async def _tap() -> None:
        generator = TouchGestureGenerator()
        points = generator.generate_tap(x, y, hold_time=hold_time)

        if _is_nodriver(page):
            _ensure_nodriver()
            from nodriver.cdp import input_ as cdp_input

            p0 = points[0]
            cdp_pt = cdp_input.TouchPoint(
                x=p0.x,
                y=p0.y,
                radius_x=p0.radius_x,
                radius_y=p0.radius_y,
                rotation_angle=p0.rotation_angle,
                force=p0.force,
                id=1,
            )
            await page.send(
                cdp_input.dispatch_touch_event(
                    type_="touchStart", touch_points=[cdp_pt]
                )
            )
            await asyncio.sleep(p0.delay)
            await page.send(
                cdp_input.dispatch_touch_event(type_="touchEnd", touch_points=[])
            )
        elif hasattr(page, "touchscreen") and hasattr(page.touchscreen, "tap"):
            await page.touchscreen.tap(x, y)
        elif _is_playwright(page):
            await page.mouse.click(x, y)
        else:
            raise ValueError(
                f"Не удалось определить тип переданного объекта: {type(page)}. "
                "Убедитесь, что передан объект Playwright (Page) или nodriver (Tab/Element)."
            )

    await _run_with_timeout(_tap(), timeout)


async def async_touch_swipe(
    page: Any,
    start: tuple[float, float],
    end: tuple[float, float],
    *,
    steps: int = 25,
    timeout: float | None = None,
) -> None:
    """Имитирует свайп пальцем по экрану в Playwright или nodriver.

    Args:
        page: Объект страницы Playwright Page или вкладки nodriver Tab.
        start: Начальные координаты (X, Y).
        end: Конечные координаты (X, Y).
        steps: Количество промежуточных шагов движения пальца.
        timeout: Таймаут выполнения операции (в секундах).
    """

    async def _swipe() -> None:
        generator = TouchGestureGenerator()
        points = generator.generate_swipe(start, end, steps=steps)

        if _is_nodriver(page):
            _ensure_nodriver()
            from nodriver.cdp import input_ as cdp_input

            for i, pt in enumerate(points):
                event_type = "touchStart" if i == 0 else "touchMove"
                cdp_pt = cdp_input.TouchPoint(
                    x=pt.x,
                    y=pt.y,
                    radius_x=pt.radius_x,
                    radius_y=pt.radius_y,
                    rotation_angle=pt.rotation_angle,
                    force=pt.force,
                    id=1,
                )
                await page.send(
                    cdp_input.dispatch_touch_event(
                        type_=event_type, touch_points=[cdp_pt]
                    )
                )
                if pt.delay > 0:
                    await asyncio.sleep(pt.delay)

            await page.send(
                cdp_input.dispatch_touch_event(type_="touchEnd", touch_points=[])
            )
        elif _is_playwright(page) or hasattr(page, "mouse"):
            await page.mouse.move(points[0].x, points[0].y)
            await page.mouse.down()
            for pt in points[1:]:
                await page.mouse.move(pt.x, pt.y)
                if pt.delay > 0:
                    await asyncio.sleep(pt.delay)
            await page.mouse.up()
        else:
            raise ValueError(
                f"Не удалось определить тип переданного объекта: {type(page)}. "
                "Убедитесь, что передан объект Playwright (Page) или nodriver (Tab/Element)."
            )

    await _run_with_timeout(_swipe(), timeout)
