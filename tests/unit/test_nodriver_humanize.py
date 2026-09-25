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
mock_input.insert_text = MagicMock(side_effect=lambda **kwargs: ("insert_text", kwargs))


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

    await async_move_mouse(tab, x=200, y=300, start=(0, 0), algorithm="windmouse")

    assert tab.send.call_count > 0
    last_call = tab.send.call_args_list[-1][0][0]
    assert last_call[0] == "dispatch_mouse_event"
    assert last_call[1]["x"] == 200
    assert last_call[1]["y"] == 300
    assert last_call[1]["type_"] == "mouseMoved"


@pytest.mark.asyncio
async def test_async_move_mouse_nodriver_wind_mouse_alias() -> None:
    """Проверяет алиас wind_mouse со змеиным регистром."""
    tab = AsyncMock()
    tab._is_nodriver = True
    tab.send = AsyncMock()

    await async_move_mouse(tab, x=250, y=350, start=(10, 10), algorithm="wind_mouse")

    assert tab.send.call_count > 0
    last_call = tab.send.call_args_list[-1][0][0]
    assert last_call[0] == "dispatch_mouse_event"
    assert last_call[1]["x"] == 250
    assert last_call[1]["y"] == 350
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


@pytest.mark.asyncio
async def test_async_type_text_nodriver_paste_dom_setter() -> None:
    """Проверяет вставку через DOM Prototype Setter в nodriver при paste_threshold."""
    tab = AsyncMock()
    tab._is_nodriver = True
    tab.find = AsyncMock()
    tab.send = AsyncMock()
    tab.evaluate = AsyncMock(return_value=True)

    mock_element = AsyncMock()
    mock_element._is_nodriver = True
    tab.find.return_value = mock_element

    text = "Длинный текст для вставки через DOM Setter" * 2
    await async_type_text(
        tab,
        selector="#input",
        text=text,
        paste_threshold=10,
        paste_delay_before=(0.0, 0.0),
        paste_delay_after=(0.0, 0.0),
    )

    # evaluate должен быть вызван с JS кодом вставки
    assert tab.evaluate.call_count == 1
    eval_call_arg = tab.evaluate.call_args_list[0][0][0]
    assert "desc.set.call" in eval_call_arg
    assert "dispatchEvent" in eval_call_arg
    # fallback send(insert_text) не должен вызываться при успешном DOM evaluate
    insert_calls = [
        c[0][0] for c in tab.send.call_args_list if c[0][0][0] == "insert_text"
    ]
    assert len(insert_calls) == 0


@pytest.mark.asyncio
async def test_async_type_text_nodriver_backspace_commands(mocker: MockerFixture) -> None:
    """Проверяет передачу commands=['deleteContentBackward'] и vk_code=8 при стирании Backspace."""
    tab = AsyncMock()
    tab._is_nodriver = True
    tab.find = AsyncMock()
    tab.send = AsyncMock()
    tab.evaluate = AsyncMock()

    mock_element = AsyncMock()
    mock_element._is_nodriver = True
    tab.find.return_value = mock_element

    mocker.patch("asyncio.sleep", new_callable=AsyncMock)

    # Запускаем ввод с гарантированной опечаткой
    await async_type_text(
        tab,
        selector="#input",
        text="test",
        error_rate=1.0,
        speed_wpm=600.0,
    )

    # Ищем вызовы dispatch_key_event для Backspace
    backspace_events = [
        c[0][0][1]
        for c in tab.send.call_args_list
        if c[0][0][0] == "dispatch_key_event"
        and c[0][0][1].get("key") == "Backspace"
        and c[0][0][1].get("type_") == "rawKeyDown"
    ]
    assert len(backspace_events) > 0
    for evt in backspace_events:
        assert evt.get("windows_virtual_key_code") == 8
        assert evt.get("native_virtual_key_code") == 8
        assert evt.get("commands") == ["deleteContentBackward"]


@pytest.mark.asyncio
async def test_async_type_text_nodriver_self_healing() -> None:
    """Проверяет вызов Self-Healing скрипта после посимвольного ввода."""
    tab = AsyncMock()
    tab._is_nodriver = True
    tab.find = AsyncMock()
    tab.send = AsyncMock()
    tab.evaluate = AsyncMock()

    mock_element = AsyncMock()
    mock_element._is_nodriver = True
    tab.find.return_value = mock_element

    await async_type_text(
        tab,
        selector="#target-input",
        text="CorrectValue",
        error_rate=0.0,
        speed_wpm=500.0,
    )

    # evaluate должен быть вызван для Self-Healing сверки
    assert tab.evaluate.call_count >= 1
    last_eval = tab.evaluate.call_args_list[-1][0][0]
    assert "current !== expected" in last_eval
    assert "#target-input" in last_eval
    assert "CorrectValue" in last_eval


@pytest.mark.asyncio
async def test_resolve_async_element_coordinates_nodriver_bounding_box() -> None:
    """Проверяет определение координат через getBoundingClientRect() в nodriver."""
    from chutils.scraping.humanize._actions_helpers import (
        _resolve_async_element_coordinates,
    )

    tab = AsyncMock()
    tab._is_nodriver = True
    tab.evaluate = AsyncMock(
        return_value={"x": 100.0, "y": 200.0, "width": 50.0, "height": 30.0}
    )
    tab.find = AsyncMock()

    coords = await _resolve_async_element_coordinates(tab, "#complex > .btn:first-child")

    assert tab.evaluate.call_count == 1
    eval_arg = tab.evaluate.call_args_list[0][0][0]
    assert "getBoundingClientRect" in eval_arg
    assert "#complex > .btn:first-child" in eval_arg

    # find() не должен вызываться, если getBoundingClientRect вернул результат
    assert tab.find.call_count == 0

    x, y = coords
    # x должен быть 100 + 50 * [0.3, 0.7] -> [115, 135]
    assert 114 <= x <= 136
    # y должен быть 200 + 30 * [0.3, 0.7] -> [209, 221]
    assert 208 <= y <= 222


@pytest.mark.asyncio
async def test_resolve_async_element_coordinates_nodriver_fallback() -> None:
    """Проверяет fallback на page.find() в nodriver, если evaluate вернул None."""
    from chutils.scraping.humanize._actions_helpers import (
        _resolve_async_element_coordinates,
    )

    tab = AsyncMock()
    tab._is_nodriver = True
    tab.evaluate = AsyncMock(return_value=None)

    mock_elem = AsyncMock()
    mock_pos = AsyncMock()
    mock_pos.x = 50.0
    mock_pos.y = 80.0
    mock_pos.width = 40.0
    mock_pos.height = 20.0
    mock_elem.get_position = AsyncMock(return_value=mock_pos)
    tab.find = AsyncMock(return_value=mock_elem)

    coords = await _resolve_async_element_coordinates(tab, "#fallback-btn")

    assert tab.evaluate.call_count == 1
    assert tab.find.call_count == 1
    x, y = coords
    assert 60 <= x <= 80
    assert 85 <= y <= 95


@pytest.mark.asyncio
async def test_async_move_mouse_timeout() -> None:
    """Проверяет выброс TimeoutError при превышении таймаута в async_move_mouse."""
    import asyncio
    tab = AsyncMock()
    tab._is_nodriver = True

    async def slow_send(*args: Any, **kwargs: Any) -> None:
        await asyncio.sleep(0.5)

    tab.send = slow_send

    with pytest.raises((TimeoutError, asyncio.TimeoutError)):
        await async_move_mouse(tab, x=100, y=100, timeout=0.02)


@pytest.mark.asyncio
async def test_async_click_timeout() -> None:
    """Проверяет выброс TimeoutError при превышении таймаута в async_click."""
    import asyncio

    from chutils.scraping.humanize.actions import async_click

    tab = AsyncMock()
    tab._is_nodriver = True

    async def slow_send(*args: Any, **kwargs: Any) -> None:
        await asyncio.sleep(0.5)

    tab.send = slow_send

    with pytest.raises((TimeoutError, asyncio.TimeoutError)):
        await async_click(tab, x=100, y=100, timeout=0.02)


@pytest.mark.asyncio
async def test_async_type_text_timeout() -> None:
    """Проверяет выброс TimeoutError при превышении таймаута в async_type_text."""
    import asyncio

    tab = AsyncMock()
    tab._is_nodriver = True
    mock_element = AsyncMock()
    mock_element._is_nodriver = True

    async def slow_focus() -> None:
        await asyncio.sleep(0.5)

    mock_element.focus = slow_focus
    tab.find = AsyncMock(return_value=mock_element)

    with pytest.raises((TimeoutError, asyncio.TimeoutError)):
        await async_type_text(tab, selector="#input", text="hello", timeout=0.02)



