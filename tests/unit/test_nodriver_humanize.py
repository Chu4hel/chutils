import importlib.util
import sys
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_mock import MockerFixture

# Настраиваем фиктивные функции для генерации CDP-команд
mock_nodriver = MagicMock()
mock_cdp = MagicMock(spec=["input_"])
mock_input = MagicMock()
mock_cdp.input_ = mock_input

mock_input.dispatch_mouse_event = MagicMock(
    side_effect=lambda **kwargs: ("dispatch_mouse_event", kwargs)
)
mock_input.dispatch_key_event = MagicMock(
    side_effect=lambda **kwargs: ("dispatch_key_event", kwargs)
)
mock_input.insert_text = MagicMock(
    side_effect=lambda **kwargs: ("insert_text", kwargs)
)


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
    mocker.patch.dict(
        sys.modules,
        {
            "nodriver": mock_nodriver,
            "nodriver.cdp": mock_cdp,
            "nodriver.cdp.input_": mock_input,
        },
    )


@pytest.mark.asyncio
async def test_async_move_mouse_nodriver() -> None:
    """Проверяет имитацию перемещения мыши с nodriver через CDP."""
    tab = AsyncMock()
    tab._is_nodriver = True
    tab.send = AsyncMock()

    await async_move_mouse(
        tab, x=200, y=300, start=(0, 0), steps=10, delay_between_steps=0.001
    )

    assert tab.send.call_count == 10
    # Проверяем, что последний вызов отправляет событие на координаты 200, 300
    last_call = tab.send.call_args_list[-1][0][0]
    assert last_call[0] == "dispatch_mouse_event"
    assert last_call[1]["x"] == 200
    assert last_call[1]["y"] == 300
    assert last_call[1]["type_"] == "mouseMoved"


@pytest.mark.asyncio
async def test_async_move_mouse_nodriver_windmouse() -> None:
    """Проверяет перемещение мыши с nodriver по алгоритму windmouse через CDP."""
    tab = AsyncMock()
    tab._is_nodriver = True
    tab.send = AsyncMock()

    await async_move_mouse(
        tab, x=200, y=300, start=(0, 0), algorithm="windmouse"
    )

    assert tab.send.call_count > 0
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

    await async_type_text(
        tab, selector="#username", text="hello", error_rate=0.0, speed_wpm=300.0
    )

    # Проверяем поиск элемента и вызов фокуса
    tab.find.assert_called_once_with("#username")
    mock_element.focus.assert_called_once()

    # Должны быть отправлены события нажатия клавиш (keydown, keyup для каждого символа)
    assert tab.send.call_count > 0
    first_send_args = tab.send.call_args_list[0][0][0]
    assert first_send_args[0] == "dispatch_key_event"
    assert "type_" in first_send_args[1]


@pytest.mark.asyncio
async def test_async_type_text_nodriver_paste_threshold(mocker: MockerFixture) -> None:
    """Проверяет адаптивную вставку длинного текста через paste_threshold в nodriver."""
    tab = AsyncMock()
    tab._is_nodriver = True
    tab.find = AsyncMock()
    tab.send = AsyncMock()

    mock_element = AsyncMock()
    mock_element._is_nodriver = True
    tab.find.return_value = mock_element

    sleep_mock = mocker.patch("asyncio.sleep", new_callable=AsyncMock)
    long_text = "Длинный текст для вставки через буфер обмена nodriver" * 2

    await async_type_text(
        tab,
        selector="#username",
        text=long_text,
        paste_threshold=40,
        paste_delay_before=(0.4, 0.7),
        paste_delay_after=(0.3, 0.5),
    )

    tab.find.assert_called_once_with("#username")
    mock_element.focus.assert_called_once()

    # Должен быть вызван send с insert_text
    insert_calls = [
        c[0][0] for c in tab.send.call_args_list if c[0][0][0] == "insert_text"
    ]
    assert len(insert_calls) == 1
    assert insert_calls[0][1]["text"] == long_text

    # dispatch_key_event не должен вызываться для посимвольного ввода
    key_events = [
        c[0][0] for c in tab.send.call_args_list if c[0][0][0] == "dispatch_key_event"
    ]
    assert len(key_events) == 0
    assert sleep_mock.call_count >= 2


@pytest.mark.asyncio
async def test_async_type_text_nodriver_delayed_fix(mocker: MockerFixture) -> None:
    """Проверяет отправку событий клавиш ArrowLeft и End при delayed_fix_rate в nodriver."""
    tab = AsyncMock()
    tab._is_nodriver = True
    tab.find = AsyncMock()
    tab.send = AsyncMock()

    mock_element = AsyncMock()
    mock_element._is_nodriver = True
    tab.find.return_value = mock_element

    mocker.patch("asyncio.sleep", new_callable=AsyncMock)
    long_text = "Тестирование nodriver с исправлением опечаток стрелками"

    await async_type_text(
        tab,
        selector="#username",
        text=long_text,
        error_rate=0.0,
        delayed_fix_rate=1.0,
        speed_wpm=500.0,
    )

    tab.find.assert_called_once_with("#username")
    mock_element.focus.assert_called_once()

    # Извлекаем все клавиши, отправленные через dispatch_key_event
    sent_keys = [
        c[0][0][1]["key"]
        for c in tab.send.call_args_list
        if c[0][0][0] == "dispatch_key_event" and "key" in c[0][0][1]
    ]

    assert "ArrowLeft" in sent_keys
    assert "Backspace" in sent_keys
    assert ("End" in sent_keys) or ("ArrowRight" in sent_keys)


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


@pytest.mark.asyncio
async def test_async_click_nodriver_hold_time(mocker: MockerFixture) -> None:
    """Проверяет удержание кнопки мыши в async_click для nodriver."""
    from chutils.scraping.humanize.actions import async_click

    tab = AsyncMock()
    tab._is_nodriver = True
    tab.send = AsyncMock()

    sleep_mock = mocker.patch("asyncio.sleep", new_callable=AsyncMock)

    await async_click(
        tab,
        x=150,
        y=250,
        hold_time=(0.07, 0.11),
    )

    # Должны быть отправлены события mousePressed и mouseReleased
    assert tab.send.call_count >= 2
    sent_types = [
        c[0][0][1]["type_"]
        for c in tab.send.call_args_list
        if c[0][0][0] == "dispatch_mouse_event"
    ]
    assert "mousePressed" in sent_types
    assert "mouseReleased" in sent_types

    # Проверяем, что был вызван asyncio.sleep с задержкой в диапазоне hold_time
    sleep_calls = [
        c[0][0] for c in sleep_mock.call_args_list if isinstance(c[0][0], (int, float))
    ]
    hold_sleeps = [s for s in sleep_calls if 0.069 <= s <= 0.111]
    assert len(hold_sleeps) >= 1


@pytest.mark.asyncio
async def test_async_type_text_key_hold_time(mocker: MockerFixture) -> None:
    """Проверяет паузу удержания клавиши (key_hold_time) в async_type_text для nodriver."""
    tab = AsyncMock()
    tab._is_nodriver = True
    tab.find = AsyncMock()
    tab.send = AsyncMock()

    mock_element = AsyncMock()
    mock_element._is_nodriver = True
    tab.find.return_value = mock_element

    sleep_mock = mocker.patch("asyncio.sleep", new_callable=AsyncMock)

    await async_type_text(
        tab,
        selector="#input",
        text="a",
        error_rate=0.0,
        speed_wpm=300.0,
        key_hold_time=(0.05, 0.08),
    )

    # Проверяем, что был sleep в диапазоне key_hold_time между keyDown и keyUp
    sleep_calls = [
        c[0][0] for c in sleep_mock.call_args_list if isinstance(c[0][0], (int, float))
    ]
    key_hold_sleeps = [s for s in sleep_calls if 0.049 <= s <= 0.081]
    assert len(key_hold_sleeps) >= 1
