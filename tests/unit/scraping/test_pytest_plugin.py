"""Тесты проверки работы pytest-плагина и фикстур chutils.scraping.testing."""

import pytest

from chutils.scraping.testing.fixtures import (
    html_snapshot_recorder,
    live_browser_session,
    local_test_server,
    mock_nodriver_tab,
    mock_playwright_page,
    mock_selenium_driver,
)
from chutils.scraping.testing.mocks import (
    MockNodriverTab,
    MockPlaywrightPage,
    MockSeleniumDriver,
)
from chutils.scraping.testing.server import LocalTestServer
from chutils.scraping.testing.session import LiveBrowserSession
from chutils.scraping.testing.snapshot import SnapshotRecorder


def test_fixture_local_test_server(local_test_server: LocalTestServer) -> None:
    """Проверяет фикстуру local_test_server."""
    assert local_test_server.is_running
    url = local_test_server.serve_html("/test", "<b>Live</b>")
    resp = local_test_server.fetch(url)
    assert resp.status == 200
    assert resp.text == "<b>Live</b>"


def test_fixture_live_browser_session(live_browser_session: LiveBrowserSession) -> None:
    """Проверяет фикстуру live_browser_session."""
    assert live_browser_session.is_active
    assert live_browser_session.user_data_dir.exists()


def test_fixture_html_snapshot_recorder(html_snapshot_recorder: SnapshotRecorder) -> None:
    """Проверяет фикстуру html_snapshot_recorder."""
    assert html_snapshot_recorder.snapshot_dir.exists()
    html_snapshot_recorder.save("plugin_test", "<p>Hello</p>")
    assert html_snapshot_recorder.load("plugin_test") == "<p>Hello</p>"


@pytest.mark.asyncio
async def test_fixture_mock_factories(
    mock_nodriver_tab: type,
    mock_playwright_page: type,
    mock_selenium_driver: type,
) -> None:
    """Проверяет фабрики моков браузеров."""
    tab = mock_nodriver_tab("<h1>Title</h1>")
    assert isinstance(tab, MockNodriverTab)
    elem = await tab.select("h1")
    assert elem.text == "Title"

    page = mock_playwright_page("<span>Playwright</span>")
    assert isinstance(page, MockPlaywrightPage)
    assert await page.locator("span").inner_text() == "Playwright"

    driver = mock_selenium_driver("<div>Selenium</div>")
    assert isinstance(driver, MockSeleniumDriver)
    assert driver.find_element("tag name", "div").text == "Selenium"
