import importlib.util
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_mock import MockerFixture

from chutils.scraping.humanize.actions import (
    async_click,
    async_move_mouse,
    async_scroll_to,
    async_type_text,
)


@pytest.fixture(autouse=True)
def mock_find_spec(mocker: MockerFixture) -> None:
    """Глушит проверку наличия библиотеки playwright, возвращая фиктивный spec."""
    orig_find_spec = importlib.util.find_spec

    def custom_find_spec(name: str, package: str | None = None) -> Any:
        if name == "playwright":
            mock_spec = MagicMock()
            mock_spec.__spec__ = MagicMock()
            return mock_spec
        return orig_find_spec(name, package)

    mocker.patch("importlib.util.find_spec", side_effect=custom_find_spec)


@pytest.mark.asyncio
async def test_async_move_mouse() -> None:
    """Проверяет имитацию перемещения мыши Playwright."""
    page = MagicMock()
    page.mouse = MagicMock()
    page.mouse.move = AsyncMock()

    await async_move_mouse(
        page, x=200, y=300, start=(0, 0), steps=10, delay_between_steps=0.001
    )

    assert page.mouse.move.call_count == 10
    last_call_args = page.mouse.move.call_args_list[-1][0]
    assert last_call_args == (200, 300)


@pytest.mark.asyncio
async def test_async_scroll_to() -> None:
    """Проверяет имитацию скроллинга Playwright."""
    page = MagicMock()
    page.evaluate = AsyncMock(return_value=0)

    await async_scroll_to(page, x=0, y=500, steps=10, delay_between_steps=0.001)

    assert page.evaluate.call_count > 2
    last_eval_call = page.evaluate.call_args_list[-1][0][0]
    assert "scrollTo" in last_eval_call
    assert "500" in last_eval_call


@pytest.mark.asyncio
async def test_async_type_text() -> None:
    """Проверяет имитацию ввода текста Playwright."""
    page = MagicMock()
    page.focus = AsyncMock()
    page.keyboard = MagicMock()
    page.keyboard.type = AsyncMock()
    page.keyboard.press = AsyncMock()

    await async_type_text(
        page, selector="#input", text="test", error_rate=0.0, speed_wpm=300.0
    )

    page.focus.assert_called_once_with("#input")
    assert page.keyboard.type.call_count == 4
    assert page.keyboard.press.call_count == 0


@pytest.mark.asyncio
async def test_async_type_text_paste_threshold(mocker: MockerFixture) -> None:
    """Проверяет адаптивную вставку длинного текста через paste_threshold."""
    page = MagicMock()
    page.focus = AsyncMock()
    page.keyboard = MagicMock()
    page.keyboard.type = AsyncMock()
    page.keyboard.insert_text = AsyncMock()

    sleep_mock = mocker.patch("asyncio.sleep", new_callable=AsyncMock)
    long_text = "Очень длинный текст для тестирования вставки через буфер обмена" * 2

    await async_type_text(
        page,
        selector="#input",
        text=long_text,
        paste_threshold=50,
        paste_delay_before=(0.4, 0.8),
        paste_delay_after=(0.3, 0.5),
    )

    page.focus.assert_called_once_with("#input")
    # Посимвольный ввод НЕ должен вызываться
    assert page.keyboard.type.call_count == 0
    # Вставка текста должна быть вызвана один раз целиком
    page.keyboard.insert_text.assert_called_once_with(long_text)
    # Должны быть паузы до и после вставки
    assert sleep_mock.call_count >= 2



@pytest.mark.asyncio
async def test_async_move_mouse_windmouse() -> None:
    """Проверяет перемещение мыши Playwright с алгоритмом WindMouse."""
    page = MagicMock()
    page.mouse = MagicMock()
    page.mouse.move = AsyncMock()

    await async_move_mouse(page, x=250, y=350, start=(0, 0), algorithm="windmouse")

    assert page.mouse.move.call_count > 5
    last_call_args = page.mouse.move.call_args_list[-1][0]
    assert last_call_args == (250, 350)


@pytest.mark.asyncio
async def test_async_click() -> None:
    """Проверяет имитацию клика мыши Playwright."""
    page = MagicMock()
    page.mouse = MagicMock()
    page.mouse.move = AsyncMock()
    page.mouse.down = AsyncMock()
    page.mouse.up = AsyncMock()

    await async_click(page, x=150, y=250)

    assert page.mouse.move.call_count > 0
    page.mouse.down.assert_called_once_with(button="left")
    page.mouse.up.assert_called_once_with(button="left")
