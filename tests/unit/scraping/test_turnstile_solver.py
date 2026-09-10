"""Unit-тесты для Cloudflare Turnstile Solver."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from chutils.scraping.humanize.turnstile import (
    detect_cf_turnstile,
    is_cf_turnstile_solved,
    solve_cf_turnstile,
)


@pytest.mark.asyncio
async def test_detect_cf_turnstile_found() -> None:
    """Проверка обнаружения виджета Turnstile."""
    mock_tab = MagicMock()
    mock_tab.evaluate = AsyncMock(
        return_value={
            "found": True,
            "solved": False,
            "type": "iframe",
            "x": 150,
            "y": 250,
            "width": 300,
            "height": 65,
            "visible": True,
        }
    )

    info = await detect_cf_turnstile(mock_tab)
    assert info is not None
    assert info["found"] is True
    assert info["visible"] is True
    assert info["x"] == 150
    assert info["y"] == 250


@pytest.mark.asyncio
async def test_detect_cf_turnstile_not_found() -> None:
    """Проверка случая, когда виджет Turnstile отсутствует."""
    mock_tab = MagicMock()
    mock_tab.evaluate = AsyncMock(return_value=None)

    info = await detect_cf_turnstile(mock_tab)
    assert info is None


@pytest.mark.asyncio
async def test_is_cf_turnstile_solved_by_token() -> None:
    """Проверка распознавания решенной капчи через token в DOM."""
    mock_tab = MagicMock()
    mock_tab.evaluate = AsyncMock(
        return_value={"found": True, "solved": True, "token": "0.abcdef123456"}
    )

    solved = await is_cf_turnstile_solved(mock_tab)
    assert solved is True


@pytest.mark.asyncio
async def test_is_cf_turnstile_solved_by_cookie() -> None:
    """Проверка распознавания решенной капчи через cf_clearance cookie."""
    mock_tab = MagicMock()
    mock_tab.evaluate = AsyncMock(return_value=None)

    with patch(
        "chutils.scraping.humanize.turnstile.extract_clearance_cookies",
        return_value={"cookies": {"cf_clearance": "valid_token_xyz"}},
    ):
        solved = await is_cf_turnstile_solved(mock_tab)
        assert solved is True


@pytest.mark.asyncio
async def test_solve_cf_turnstile_already_solved() -> None:
    """Проверка решения капчи, если она уже решена в начале вызова."""
    mock_tab = MagicMock()
    mock_tab.evaluate = AsyncMock(
        return_value={"found": True, "solved": True, "token": "0.token"}
    )

    with patch("chutils.scraping.humanize.turnstile.async_click") as mock_click:
        result = await solve_cf_turnstile(mock_tab, timeout=2.0)
        assert result is True
        assert not mock_click.called


@pytest.mark.asyncio
async def test_solve_cf_turnstile_success() -> None:
    """Проверка полного цикла: обнаружение, клик и подтверждение решения."""
    mock_tab = MagicMock()

    # Сначала виджет обнаружен, затем при повторной проверке решен
    state = {"solved": False}

    async def mock_eval(script: str) -> dict[str, object] | None:
        if state["solved"]:
            return {"found": True, "solved": True, "token": "0.solution_token"}
        return {
            "found": True,
            "solved": False,
            "type": "iframe",
            "x": 100,
            "y": 200,
            "width": 300,
            "height": 65,
            "visible": True,
        }

    mock_tab.evaluate = mock_eval

    async def mock_click(tab: object, **kwargs: object) -> None:
        state["solved"] = True

    with (
        patch(
            "chutils.scraping.humanize.turnstile.async_click",
            side_effect=mock_click,
        ) as click_spy,
        patch(
            "chutils.scraping.humanize.turnstile.async_human_sleep",
            AsyncMock(),
        ),
    ):
        result = await solve_cf_turnstile(
            mock_tab,
            timeout=5.0,
            check_interval=0.05,
            click_delay=(0.0, 0.0),
        )
        assert result is True
        assert click_spy.called
        call_kwargs = click_spy.call_args.kwargs
        # Проверяем, что координаты попадают в диапазон виджета
        assert call_kwargs["x"] >= 100
        assert call_kwargs["y"] >= 200


@pytest.mark.asyncio
async def test_solve_cf_turnstile_timeout_return_false() -> None:
    """Проверка таймаута без исключения (raise_on_failure=False)."""
    mock_tab = MagicMock()
    mock_tab.evaluate = AsyncMock(return_value=None)

    with patch(
        "chutils.scraping.humanize.turnstile.extract_clearance_cookies",
        return_value={"cookies": {}},
    ):
        result = await solve_cf_turnstile(
            mock_tab,
            timeout=0.1,
            check_interval=0.02,
            raise_on_failure=False,
        )
        assert result is False


@pytest.mark.asyncio
async def test_solve_cf_turnstile_timeout_raise_error() -> None:
    """Проверка таймаута с исключением (raise_on_failure=True)."""
    mock_tab = MagicMock()
    mock_tab.evaluate = AsyncMock(return_value=None)

    with (
        patch(
            "chutils.scraping.humanize.turnstile.extract_clearance_cookies",
            return_value={"cookies": {}},
        ),
        pytest.raises(RuntimeError, match="Не удалось решить Cloudflare Turnstile"),
    ):
        await solve_cf_turnstile(
            mock_tab,
            timeout=0.1,
            check_interval=0.02,
            raise_on_failure=True,
        )


def test_turnstile_inspect_js_script_structure() -> None:
    """Проверка структуры JavaScript-инспектора Turnstile: Shadow DOM, viewport и scrollIntoView."""
    from chutils.scraping.humanize.turnstile import TURNSTILE_INSPECT_JS

    # 1. Не должно быть scrollX или scrollY, так как CDP клики используют Client Viewport
    assert "window.scrollX" not in TURNSTILE_INSPECT_JS
    assert "window.scrollY" not in TURNSTILE_INSPECT_JS

    # 2. Должен использовать координаты rect.left и rect.top (Viewport)
    assert "rect.left" in TURNSTILE_INSPECT_JS
    assert "rect.top" in TURNSTILE_INSPECT_JS

    # 3. Должен присутствовать рекурсивный поиск в shadowRoot
    assert "shadowRoot" in TURNSTILE_INSPECT_JS

    # 4. Должен присутствовать вызов scrollIntoView для центрирования
    assert "scrollIntoView" in TURNSTILE_INSPECT_JS

    # 5. Должна проверяться интерактивность (стили, pointer-events, data-state)
    assert "pointerEvents" in TURNSTILE_INSPECT_JS
    assert "data-state" in TURNSTILE_INSPECT_JS


@pytest.mark.asyncio
async def test_solve_cf_turnstile_waits_for_interactive() -> None:
    """Проверка, что solve_cf_turnstile не кликает, пока виджет non-interactive (например, spinner)."""
    mock_tab = MagicMock()
    interactions = {"clicks": 0, "eval_count": 0}

    async def mock_eval(script: str) -> dict[str, object] | None:
        interactions["eval_count"] += 1
        # На первом вызове виджет найден, но non-interactive (спиннер / checking)
        if interactions["eval_count"] == 1:
            return {
                "found": True,
                "solved": False,
                "type": "container",
                "x": 100,
                "y": 200,
                "width": 300,
                "height": 65,
                "visible": True,
                "interactive": False,
            }
        # На втором вызове виджет стал interactive
        if interactions["eval_count"] == 2:
            return {
                "found": True,
                "solved": False,
                "type": "iframe",
                "x": 100,
                "y": 200,
                "width": 300,
                "height": 65,
                "visible": True,
                "interactive": True,
            }
        # На третьем вызове капча решена
        return {"found": True, "solved": True, "token": "0.solution_token"}

    mock_tab.evaluate = mock_eval

    async def mock_click(tab: object, **kwargs: object) -> None:
        interactions["clicks"] += 1

    with (
        patch(
            "chutils.scraping.humanize.turnstile.async_click", side_effect=mock_click
        ),
        patch("chutils.scraping.humanize.turnstile.async_human_sleep", AsyncMock()),
    ):
        result = await solve_cf_turnstile(
            mock_tab,
            timeout=5.0,
            check_interval=0.01,
            click_delay=(0.0, 0.0),
        )
        assert result is True
        # Клик должен быть вызван ровно 1 раз, когда виджет стал interactive
        assert interactions["clicks"] == 1
        assert interactions["eval_count"] >= 3


@pytest.mark.asyncio
async def test_solve_cf_turnstile_box_model_fallback() -> None:
    """Проверка fallback на CDP get_box_model, если JS возвращает нулевые размеры."""
    mock_tab = MagicMock()
    mock_tab.evaluate = AsyncMock(
        return_value={
            "found": True,
            "solved": False,
            "type": "iframe",
            "x": 0,
            "y": 0,
            "width": 0,
            "height": 0,
            "visible": False,
            "interactive": False,
        }
    )

    # Мокируем CDP fallback метод tab.get_position или find
    mock_element = MagicMock()
    mock_element.get_position = AsyncMock(
        return_value=MagicMock(x=120, y=220, width=300, height=65)
    )
    mock_tab.find = AsyncMock(return_value=mock_element)

    # После клика статус solved
    state = {"clicked": False}

    async def mock_click(tab: object, **kwargs: object) -> None:
        state["clicked"] = True
        mock_tab.evaluate = AsyncMock(
            return_value={"found": True, "solved": True, "token": "0.token"}
        )

    with (
        patch(
            "chutils.scraping.humanize.turnstile.async_click", side_effect=mock_click
        ),
        patch("chutils.scraping.humanize.turnstile.async_human_sleep", AsyncMock()),
    ):
        result = await solve_cf_turnstile(
            mock_tab,
            timeout=2.0,
            check_interval=0.01,
            click_delay=(0.0, 0.0),
        )
        assert result is True
        assert state["clicked"] is True


@pytest.mark.asyncio
async def test_solve_cf_turnstile_custom_click_offset() -> None:
    """Проверка переопределения смещения клика через параметр click_offset."""
    mock_tab = MagicMock()
    mock_tab.evaluate = AsyncMock(
        return_value={
            "found": True,
            "solved": False,
            "type": "iframe",
            "x": 100,
            "y": 200,
            "width": 300,
            "height": 65,
            "visible": True,
            "interactive": True,
        }
    )

    clicked_coords: dict[str, int] = {}

    async def mock_click(tab: object, **kwargs: object) -> None:
        clicked_coords["x"] = int(kwargs["x"])
        clicked_coords["y"] = int(kwargs["y"])
        # Сразу отмечаем решенной
        mock_tab.evaluate = AsyncMock(
            return_value={"found": True, "solved": True, "token": "0.token"}
        )

    with (
        patch(
            "chutils.scraping.humanize.turnstile.async_click", side_effect=mock_click
        ),
        patch("chutils.scraping.humanize.turnstile.async_human_sleep", AsyncMock()),
    ):
        result = await solve_cf_turnstile(
            mock_tab,
            timeout=2.0,
            check_interval=0.01,
            click_delay=(0.0, 0.0),
            click_offset=(60.0, 30.0),
        )
        assert result is True
        # x = 100 + 60 = 160, y = 200 + 30 = 230
        assert clicked_coords["x"] == 160
        assert clicked_coords["y"] == 230


@pytest.mark.asyncio
async def test_solve_cf_turnstile_compact_widget() -> None:
    """Проверка адаптивного смещения для компактного виджета (compact mode)."""
    mock_tab = MagicMock()
    # Компактный виджет 130x120
    mock_tab.evaluate = AsyncMock(
        return_value={
            "found": True,
            "solved": False,
            "type": "container",
            "x": 50,
            "y": 80,
            "width": 130,
            "height": 120,
            "visible": True,
            "interactive": True,
        }
    )

    clicked_coords: dict[str, int] = {}

    async def mock_click(tab: object, **kwargs: object) -> None:
        clicked_coords["x"] = int(kwargs["x"])
        clicked_coords["y"] = int(kwargs["y"])
        mock_tab.evaluate = AsyncMock(
            return_value={"found": True, "solved": True, "token": "0.token"}
        )

    with (
        patch(
            "chutils.scraping.humanize.turnstile.async_click", side_effect=mock_click
        ),
        patch("chutils.scraping.humanize.turnstile.async_human_sleep", AsyncMock()),
    ):
        result = await solve_cf_turnstile(
            mock_tab,
            timeout=2.0,
            check_interval=0.01,
            click_delay=(0.0, 0.0),
        )
        assert result is True
        # В компактном режиме смещение X ~ 130 * 0.22 ~ 28px, Y ~ 120 * 0.32 ~ 38px
        assert 70 <= clicked_coords["x"] <= 90
        assert 110 <= clicked_coords["y"] <= 130


@pytest.mark.asyncio
async def test_solve_cf_turnstile_retry_on_expired() -> None:
    """Проверка сброса состояния clicked и повторного клика при переходе виджета в expired."""
    mock_tab = MagicMock()
    step = {"count": 0, "clicks": 0}

    async def mock_eval(script: str) -> dict[str, object] | None:
        step["count"] += 1
        # 1-й вызов: интерактивный виджет
        if step["count"] == 1:
            return {
                "found": True,
                "solved": False,
                "type": "iframe",
                "x": 100,
                "y": 200,
                "width": 300,
                "height": 65,
                "visible": True,
                "interactive": True,
                "data_state": "",
            }
        # 2-й вызов (после первого клика): виджет проэкспайрился
        if step["count"] == 2:
            return {
                "found": True,
                "solved": False,
                "type": "iframe",
                "x": 100,
                "y": 200,
                "width": 300,
                "height": 65,
                "visible": True,
                "interactive": True,
                "data_state": "expired",
            }
        # 3-й вызов (после второго клика): решено
        return {"found": True, "solved": True, "token": "0.solution_token"}

    mock_tab.evaluate = mock_eval

    async def mock_click(tab: object, **kwargs: object) -> None:
        step["clicks"] += 1

    with (
        patch(
            "chutils.scraping.humanize.turnstile.async_click", side_effect=mock_click
        ),
        patch("chutils.scraping.humanize.turnstile.async_human_sleep", AsyncMock()),
    ):
        result = await solve_cf_turnstile(
            mock_tab,
            timeout=5.0,
            check_interval=0.01,
            click_delay=(0.0, 0.0),
        )
        assert result is True
        # Было произведено 2 клика: первоначальный и повторный после expired
        assert step["clicks"] == 2
