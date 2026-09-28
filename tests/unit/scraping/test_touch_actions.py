"""Unit-тесты для генератора сенсорных жестов и действий touch."""

import importlib.util
import math
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_mock import MockerFixture

from chutils.scraping.humanize.actions import (
    TouchGestureGenerator,
    TouchPoint,
    async_touch_swipe,
    async_touch_tap,
)


@pytest.fixture(autouse=True)
def mock_find_spec(mocker: MockerFixture) -> None:
    """Глушит проверку наличия библиотеки nodriver, возвращая фиктивный spec."""
    orig_find_spec = importlib.util.find_spec

    def custom_find_spec(name: str, package: str | None = None) -> Any:
        if name == "nodriver":
            mock_spec = MagicMock()
            mock_spec.__spec__ = MagicMock()
            return mock_spec
        return orig_find_spec(name, package)

    mocker.patch("importlib.util.find_spec", side_effect=custom_find_spec)


def test_touch_point_creation() -> None:
    """Проверка структуры и значений по умолчанию TouchPoint."""
    tp = TouchPoint(x=100.0, y=200.0, radius_x=14.0, radius_y=16.0, force=0.8, delay=0.02)
    assert tp.x == 100.0
    assert tp.y == 200.0
    assert tp.radius_x == 14.0
    assert tp.radius_y == 16.0
    assert tp.force == 0.8
    assert tp.delay == 0.02


def test_touch_gesture_generator_tap() -> None:
    """Проверка генерации одиночного касания (tap)."""
    generator = TouchGestureGenerator()
    points = generator.generate_tap(150.0, 250.0, hold_time=0.07)

    assert len(points) >= 2
    # Начальная точка касания
    start_pt = points[0]
    assert math.isclose(start_pt.x, 150.0, abs_tol=5.0)
    assert math.isclose(start_pt.y, 250.0, abs_tol=5.0)
    assert start_pt.force > 0
    assert start_pt.radius_x > 0

    # Проверка задержки удержания пальца
    total_delay = sum(p.delay for p in points)
    assert total_delay >= 0.05


def test_touch_gesture_generator_swipe() -> None:
    """Проверка генерации траектории свайпа (swipe)."""
    generator = TouchGestureGenerator()
    start = (100.0, 500.0)
    end = (100.0, 100.0)
    points = generator.generate_swipe(start, end, steps=20)

    assert len(points) == 20
    # Начальная точка близка к start
    assert math.isclose(points[0].x, start[0], abs_tol=5.0)
    assert math.isclose(points[0].y, start[1], abs_tol=5.0)
    # Конечная точка близка к end
    assert math.isclose(points[-1].x, end[0], abs_tol=5.0)
    assert math.isclose(points[-1].y, end[1], abs_tol=5.0)

    # Сила нажатия в середине траектории выше, чем на краях (реалистичный нажим)
    mid_idx = len(points) // 2
    assert points[mid_idx].force >= points[0].force
    assert points[mid_idx].force >= points[-1].force

    # Радиус пятна контакта положительный
    for p in points:
        assert p.radius_x > 0
        assert p.radius_y > 0


def test_touch_gesture_generator_pinch() -> None:
    """Проверка генерации жеста сведения/разведения двух пальцев (pinch/zoom)."""
    generator = TouchGestureGenerator()
    center = (200.0, 300.0)
    pairs = generator.generate_pinch(center, start_distance=100.0, end_distance=300.0, steps=15)

    assert len(pairs) == 15
    # Первая пара точек имеет расстояние ~100
    p1_first, p2_first = pairs[0]
    first_dist = math.hypot(p1_first.x - p2_first.x, p1_first.y - p2_first.y)
    assert math.isclose(first_dist, 100.0, abs_tol=10.0)

    # Последняя пара точек имеет расстояние ~300
    p1_last, p2_last = pairs[-1]
    last_dist = math.hypot(p1_last.x - p2_last.x, p1_last.y - p2_last.y)
    assert math.isclose(last_dist, 300.0, abs_tol=10.0)

    # Центр масс между пальцами остается близким к center
    mid_x = (p1_first.x + p2_first.x) / 2
    mid_y = (p1_first.y + p2_first.y) / 2
    assert math.isclose(mid_x, center[0], abs_tol=10.0)
    assert math.isclose(mid_y, center[1], abs_tol=10.0)


@pytest.mark.asyncio
async def test_async_touch_tap_playwright() -> None:
    """Проверка async_touch_tap на объекте Playwright."""
    page = MagicMock()
    page.touchscreen = MagicMock()
    page.touchscreen.tap = AsyncMock()

    # Playwright page duck typing
    del page.send  # точно не nodriver

    await async_touch_tap(page, 120, 240)
    page.touchscreen.tap.assert_called_once()
    args, _ = page.touchscreen.tap.call_args
    assert math.isclose(args[0], 120, abs_tol=5.0)
    assert math.isclose(args[1], 240, abs_tol=5.0)


@pytest.mark.asyncio
async def test_async_touch_tap_nodriver() -> None:
    """Проверка async_touch_tap на объекте nodriver."""
    tab = MagicMock()
    tab._is_nodriver = True
    tab.send = AsyncMock()

    # Мокаем cdp input_ для nodriver
    mock_input = MagicMock()
    mock_input.dispatch_touch_event = MagicMock(return_value="touch_event")
    mock_input.TouchPoint = MagicMock(side_effect=lambda **kwargs: kwargs)

    mock_cdp = MagicMock()
    mock_cdp.input_ = mock_input
    mock_nodriver = MagicMock()
    mock_nodriver.cdp = mock_cdp

    import sys
    sys.modules["nodriver"] = mock_nodriver
    sys.modules["nodriver.cdp"] = mock_cdp
    sys.modules["nodriver.cdp.input_"] = mock_input

    try:
        await async_touch_tap(tab, 200, 300)
        assert tab.send.called
        assert mock_input.dispatch_touch_event.called
    finally:
        sys.modules.pop("nodriver", None)
        sys.modules.pop("nodriver.cdp", None)
        sys.modules.pop("nodriver.cdp.input_", None)


@pytest.mark.asyncio
async def test_async_touch_swipe_playwright() -> None:
    """Проверка async_touch_swipe на объекте Playwright."""
    page = MagicMock()
    page.mouse = MagicMock()
    page.mouse.move = AsyncMock()
    page.mouse.down = AsyncMock()
    page.mouse.up = AsyncMock()

    del page.send  # не nodriver

    await async_touch_swipe(page, (100, 400), (100, 100), steps=10)
    assert page.mouse.down.called
    assert page.mouse.move.called
    assert page.mouse.up.called


@pytest.mark.asyncio
async def test_async_touch_swipe_nodriver() -> None:
    """Проверка async_touch_swipe на объекте nodriver."""
    tab = MagicMock()
    tab._is_nodriver = True
    tab.send = AsyncMock()

    mock_input = MagicMock()
    mock_input.dispatch_touch_event = MagicMock(return_value="touch_event")
    mock_input.TouchPoint = MagicMock(side_effect=lambda **kwargs: kwargs)

    mock_cdp = MagicMock()
    mock_cdp.input_ = mock_input
    mock_nodriver = MagicMock()
    mock_nodriver.cdp = mock_cdp

    import sys
    sys.modules["nodriver"] = mock_nodriver
    sys.modules["nodriver.cdp"] = mock_cdp
    sys.modules["nodriver.cdp.input_"] = mock_input

    try:
        await async_touch_swipe(tab, (100, 500), (100, 100), steps=5)
        assert tab.send.called
        assert mock_input.dispatch_touch_event.called
    finally:
        sys.modules.pop("nodriver", None)
        sys.modules.pop("nodriver.cdp", None)
        sys.modules.pop("nodriver.cdp.input_", None)
