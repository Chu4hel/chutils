import importlib.util
import sys
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_mock import MockerFixture

# Мокаем библиотеки
mock_playwright = MagicMock()
mock_selenium = MagicMock()
mock_nodriver = MagicMock()
mock_cdp = MagicMock()
mock_input = MagicMock()
mock_cdp.input = mock_input


@pytest.fixture(autouse=True)
def mock_sys_modules(mocker: MockerFixture) -> None:
    """Мокает библиотеки на уровне sys.modules только на время тестов в этом файле."""
    mocker.patch.dict(sys.modules, {
        "playwright": mock_playwright,
        "selenium": mock_selenium,
        "nodriver": mock_nodriver,
        "nodriver.cdp": mock_cdp,
        "nodriver.cdp.input": mock_input,
    })


@pytest.fixture(autouse=True)
def mock_find_specs(mocker: MockerFixture) -> None:
    """Глушит проверку наличия всех библиотек, возвращая фиктивные specs."""
    orig_find_spec = importlib.util.find_spec

    def custom_find_spec(name: str, package: str | None = None) -> Any:
        if name in ("playwright", "selenium", "nodriver"):
            mock_spec = MagicMock()
            mock_spec.__spec__ = MagicMock()
            return mock_spec
        return orig_find_spec(name, package)

    mocker.patch("importlib.util.find_spec", side_effect=custom_find_spec)


from chutils.scraping.humanize.warmer import ProfileWarmer, SyncProfileWarmer


@pytest.mark.asyncio
async def test_profile_warmer_playwright() -> None:
    """Тестирует ProfileWarmer с Playwright Page."""
    page = MagicMock()
    page.goto = AsyncMock()
    page.url = "https://example.com"
    # Имитируем возврат текущего URL и списка внутренних ссылок
    page.evaluate = AsyncMock(side_effect=lambda js, *args: (
        "https://example.com" if "window.location.href" in js
        else ["/about", "/contact"]
    ))

    mock_element = AsyncMock()
    page.query_selector_all = AsyncMock(return_value=[mock_element])

    # Патчим функции мыши, скролла и выбор действия, чтобы избежать реальных задержек и сделать тест детерминированным
    with patch("chutils.scraping.humanize.warmer.async_move_mouse", AsyncMock()), \
         patch("chutils.scraping.humanize.warmer.async_scroll_to", AsyncMock()), \
         patch("chutils.scraping.humanize.warmer.async_human_sleep", AsyncMock()), \
         patch("random.choice", return_value="click_link"):

        warmer = ProfileWarmer(page)
        await warmer.warm_up(
            sites=["https://example.com"],
            sites_count=1,
            duration_per_site=(0.01, 0.02),
            click_random_links=True
        )

        page.goto.assert_any_call("https://example.com")
        assert page.evaluate.call_count > 0


@pytest.mark.asyncio
async def test_profile_warmer_nodriver() -> None:
    """Тестирует ProfileWarmer с nodriver Tab."""
    tab = AsyncMock()
    tab._is_nodriver = True
    tab.get = AsyncMock()
    tab.url = "https://example.com"
    tab.evaluate = AsyncMock(side_effect=lambda js, *args: (
        "https://example.com" if "window.location.href" in js
        else ["/about", "/contact"]
    ))

    with patch("chutils.scraping.humanize.warmer.async_move_mouse", AsyncMock()), \
         patch("chutils.scraping.humanize.warmer.async_scroll_to", AsyncMock()), \
         patch("chutils.scraping.humanize.warmer.async_human_sleep", AsyncMock()), \
         patch("random.choice", return_value="click_link"):

        warmer = ProfileWarmer(tab)
        await warmer.warm_up(
            sites=["https://example.com"],
            sites_count=1,
            duration_per_site=(0.01, 0.02),
            click_random_links=True
        )

        tab.get.assert_any_call("https://example.com")


def test_profile_warmer_selenium() -> None:
    """Тестирует SyncProfileWarmer с Selenium WebDriver."""
    driver = MagicMock()
    driver.get = MagicMock()
    driver.current_url = "https://example.com"
    driver.execute_script = MagicMock(side_effect=lambda js, *args: (
        "https://example.com" if "window.location.href" in js
        else ["/about", "/contact"]
    ))

    with patch("chutils.scraping.humanize.warmer.move_mouse", MagicMock()), \
         patch("chutils.scraping.humanize.warmer.scroll_to", MagicMock()), \
         patch("chutils.scraping.humanize.warmer.human_sleep", MagicMock()), \
         patch("random.choice", return_value="click_link"):

        warmer = SyncProfileWarmer(driver)
        warmer.warm_up(
            sites=["https://example.com"],
            sites_count=1,
            duration_per_site=(0.01, 0.02),
            click_random_links=True
        )

        driver.get.assert_any_call("https://example.com")
