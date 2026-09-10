"""Unit-тесты для модуля запуска nodriver (launch_nodriver, nodriver_session)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from chutils.scraping.humanize.config import AntidetectConfig
from chutils.scraping.nodriver import (
    _get_nodriver_module,
    launch_nodriver,
    nodriver_session,
)


def test_get_nodriver_module_not_installed() -> None:
    """Проверка выброса понятной ошибки при отсутствии nodriver."""
    with patch.dict("sys.modules", {"nodriver": None}):
        with patch(
            "builtins.__import__", side_effect=ImportError("No module named 'nodriver'")
        ):
            with pytest.raises(
                ImportError,
                match="Для использования nodriver необходимо установить библиотеку",
            ):
                _get_nodriver_module()


@pytest.mark.asyncio
async def test_launch_nodriver_default() -> None:
    """Проверка запуска nodriver со стандартным пресетом AntidetectConfig и stealth-аргументами."""
    mock_uc = MagicMock()
    mock_browser = MagicMock()
    mock_tab = MagicMock()
    mock_browser.main_tab = mock_tab
    mock_uc.start = AsyncMock(return_value=mock_browser)

    with (
        patch("chutils.scraping.nodriver._get_nodriver_module", return_value=mock_uc),
        patch.object(
            AntidetectConfig, "apply_to_nodriver", new_callable=AsyncMock
        ) as mock_apply,
    ):
        browser = await launch_nodriver(headless=True)
        assert browser is mock_browser
        assert mock_uc.start.called

        _, kwargs = mock_uc.start.call_args
        assert kwargs["headless"] is True
        args = kwargs["browser_args"]
        assert any("--disable-blink-features=AutomationControlled" in a for a in args)

        # Проверяем, что к вкладке применен стелс-конфиг
        assert mock_apply.called


@pytest.mark.asyncio
async def test_launch_nodriver_with_proxy_and_custom_args() -> None:
    """Проверка добавления аргументов прокси и пользовательских флагов."""
    mock_uc = MagicMock()
    mock_browser = MagicMock()
    mock_browser.main_tab = MagicMock()
    mock_uc.start = AsyncMock(return_value=mock_browser)

    with (
        patch("chutils.scraping.nodriver._get_nodriver_module", return_value=mock_uc),
        patch(
            "chutils.scraping.nodriver.AntidetectConfig.apply_to_nodriver", AsyncMock()
        ),
    ):
        await launch_nodriver(
            proxy="http://1.2.3.4:8080",
            browser_args=["--custom-flag=test"],
        )
        _, kwargs = mock_uc.start.call_args
        args = kwargs["browser_args"]
        assert "--custom-flag=test" in args
        assert any("--proxy-server=" in a for a in args)


@pytest.mark.asyncio
async def test_nodriver_session_context_manager() -> None:
    """Проверка корректного закрытия браузера в nodriver_session."""
    mock_uc = MagicMock()
    mock_browser = MagicMock()
    mock_browser.main_tab = MagicMock()
    mock_browser.stop = AsyncMock()
    mock_uc.start = AsyncMock(return_value=mock_browser)

    with (
        patch("chutils.scraping.nodriver._get_nodriver_module", return_value=mock_uc),
        patch(
            "chutils.scraping.nodriver.AntidetectConfig.apply_to_nodriver", AsyncMock()
        ),
    ):
        async with nodriver_session(headless=False) as browser:
            assert browser is mock_browser
            assert not mock_browser.stop.called

        # После выхода из контекста вызван stop()
        assert mock_browser.stop.called


@pytest.mark.asyncio
async def test_launch_nodriver_user_data_dir_and_executable() -> None:
    """Проверка передачи user_data_dir и browser_executable_path в uc.start."""
    mock_uc = MagicMock()
    mock_browser = MagicMock()
    mock_browser.main_tab = MagicMock()
    mock_uc.start = AsyncMock(return_value=mock_browser)

    with (
        patch("chutils.scraping.nodriver._get_nodriver_module", return_value=mock_uc),
        patch(
            "chutils.scraping.nodriver.AntidetectConfig.apply_to_nodriver", AsyncMock()
        ),
    ):
        await launch_nodriver(
            user_data_dir="/tmp/chrome_profile",
            browser_executable_path="/usr/bin/google-chrome",
        )
        _, kwargs = mock_uc.start.call_args
        assert kwargs["user_data_dir"] == "/tmp/chrome_profile"
        assert kwargs["browser_executable_path"] == "/usr/bin/google-chrome"


def test_scraping_module_exports() -> None:
    """Проверка ленивого экспорта launch_nodriver и nodriver_session из chutils.scraping."""
    from chutils import scraping

    assert hasattr(scraping, "launch_nodriver")
    assert hasattr(scraping, "nodriver_session")
    assert "launch_nodriver" in scraping.__all__
    assert "nodriver_session" in scraping.__all__
