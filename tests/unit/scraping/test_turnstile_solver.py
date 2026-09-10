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
