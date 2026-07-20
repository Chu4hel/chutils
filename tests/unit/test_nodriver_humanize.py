import importlib.util
import sys
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_mock import MockerFixture

# Настраиваем фиктивные функции для генерации CDP-команд
mock_nodriver = MagicMock()
mock_cdp = MagicMock()
mock_input = MagicMock()
mock_cdp.input = mock_input

mock_input.dispatch_mouse_event = MagicMock(side_effect=lambda **kwargs: ("dispatch_mouse_event", kwargs))
mock_input.dispatch_key_event = MagicMock(side_effect=lambda **kwargs: ("dispatch_key_event", kwargs))


from chutils.scraping.humanize.actions import (
    async_move_mouse,
    async_scroll_to,
    async_type_text,
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


@pytest.fixture(autouse=True)
def mock_sys_modules(mocker: MockerFixture) -> None:
    """Мокает nodriver на уровне sys.modules только на время выполнения тестов в этом модуле."""
    mocker.patch.dict(sys.modules, {
        "nodriver": mock_nodriver,
        "nodriver.cdp": mock_cdp,
        "nodriver.cdp.input": mock_input,
    })


@pytest.mark.asyncio
async def test_async_move_mouse_nodriver() -> None:
    """Проверяет имитацию перемещения мыши с nodriver через CDP."""
    tab = AsyncMock()
    tab._is_nodriver = True
    tab.send = AsyncMock()

    await async_move_mouse(tab, x=200, y=300, start=(0, 0), steps=10, delay_between_steps=0.001)

    assert tab.send.call_count == 10
    # Проверяем, что последний вызов отправляет событие на координаты 200, 300
    last_call = tab.send.call_args_list[-1][0][0]
    assert last_call[0] == "dispatch_mouse_event"
    assert last_call[1]["x"] == 200
    assert last_call[1]["y"] == 300
    assert last_call[1]["type_"] == "mouseMoved"


@pytest.mark.asyncio
async def test_async_scroll_to_nodriver() -> None:
    """Проверяет имитацию скроллинга с nodriver."""
    tab = AsyncMock()
    tab._is_nodriver = True
    tab.evaluate = AsyncMock()

    await async_scroll_to(tab, x=100, y=500, steps=10, delay_between_steps=0.001)

    assert tab.evaluate.call_count == 12
    last_eval = tab.evaluate.call_args_list[-1][0][0]
    assert "scrollTo" in last_eval
    assert "100" in last_eval
    assert "500" in last_eval


@pytest.mark.asyncio
async def test_async_type_text_nodriver() -> None:
    """Проверяет имитацию ввода текста с опечатками и Backspace с nodriver."""
    tab = AsyncMock()
    tab._is_nodriver = True
    tab.find = AsyncMock()
    tab.send = AsyncMock()
    tab.evaluate = AsyncMock()

    mock_element = AsyncMock()
    mock_element._is_nodriver = True
    tab.find.return_value = mock_element

    await async_type_text(tab, selector="#username", text="hello", error_rate=0.0, speed_wpm=300.0)

    # Проверяем поиск элемента и вызов фокуса
    tab.find.assert_called_once_with("#username")
    mock_element.focus.assert_called_once()

    # Должны быть отправлены события нажатия клавиш (keydown, keyup для каждого символа)
    assert tab.send.call_count > 0
    first_send_args = tab.send.call_args_list[0][0][0]
    assert first_send_args[0] == "dispatch_key_event"
    assert "type_" in first_send_args[1]


@pytest.mark.asyncio
async def test_invalid_type_raises_value_error() -> None:
    """Проверяет, что передача объекта неизвестного типа выбрасывает ValueError."""
    with pytest.raises(ValueError, match="Не удалось определить тип"):
        await async_move_mouse(12345, x=10, y=10)

    with pytest.raises(ValueError, match="Не удалось определить тип"):
        await async_scroll_to(12345, x=10, y=10)

    with pytest.raises(ValueError, match="Не удалось определить тип"):
        await async_type_text(12345, selector="#input", text="test")


@pytest.mark.asyncio
async def test_ensure_nodriver_raises_dependency_error(mocker: MockerFixture) -> None:
    """Проверяет, что при отсутствии nodriver выбрасывается OptionalDependencyError."""
    # Временно удаляем nodriver из sys.modules
    old_nodriver = sys.modules.pop("nodriver", None)
    
    try:
        # Переопределяем find_spec, чтобы возвращал None для nodriver
        mocker.patch("importlib.util.find_spec", return_value=None)

        # Создаем объект, похожий на nodriver
        tab = MagicMock()
        tab._is_nodriver = True
        tab.send = AsyncMock()

        with pytest.raises(Exception) as exc_info:
            await async_move_mouse(tab, x=10, y=10)

        assert "OptionalDependencyError" in type(exc_info.value).__name__
        assert "nodriver" in str(exc_info.value)
    finally:
        # Восстанавливаем nodriver
        if old_nodriver is not None:
            sys.modules["nodriver"] = old_nodriver
