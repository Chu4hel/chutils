"""Тесты для модуля cookie/headers bridge (extract_clearance_cookies и from_browser_session)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from chutils.http.tls_client import TLSAsyncClient, TLSSession
from chutils.scraping.humanize.antidetect import extract_clearance_cookies


@pytest.mark.asyncio
async def test_extract_clearance_cookies_playwright() -> None:
    """extract_clearance_cookies извлекает cookies и user_agent из Playwright Page/Context."""
    mock_context = MagicMock()
    mock_context.cookies = AsyncMock(
        return_value=[
            {
                "name": "cf_clearance",
                "value": "secret_clearance_123",
                "domain": "example.com",
            },
            {"name": "session_id", "value": "sess_456", "domain": "example.com"},
        ]
    )
    mock_page = MagicMock()
    mock_page.context = mock_context
    mock_page.evaluate = AsyncMock(
        return_value="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"
    )

    result = await extract_clearance_cookies(mock_page)

    assert result["cookies"]["cf_clearance"] == "secret_clearance_123"
    assert result["cookies"]["session_id"] == "sess_456"
    assert (
        result["user_agent"]
        == "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"
    )


def test_extract_clearance_cookies_selenium() -> None:
    """extract_clearance_cookies извлекает cookies и user_agent из Selenium WebDriver."""
    mock_driver = MagicMock()
    del mock_driver.context
    mock_driver.get_cookies.return_value = [
        {"name": "cf_clearance", "value": "selenium_cf_789"},
    ]
    mock_driver.execute_script.return_value = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) SeleniumUA"
    )

    result = extract_clearance_cookies(mock_driver)

    assert result["cookies"]["cf_clearance"] == "selenium_cf_789"
    assert (
        result["user_agent"] == "Mozilla/5.0 (Windows NT 10.0; Win64; x64) SeleniumUA"
    )


@pytest.mark.asyncio
async def test_extract_clearance_cookies_nodriver(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """extract_clearance_cookies извлекает cookies из Nodriver Tab."""
    import sys

    mock_network = MagicMock()
    mock_network.get_cookies.return_value = "cdp_cmd"
    monkeypatch.setitem(sys.modules, "nodriver", MagicMock())
    monkeypatch.setitem(sys.modules, "nodriver.cdp", MagicMock())
    monkeypatch.setitem(sys.modules, "nodriver.cdp.network", mock_network)

    mock_tab = MagicMock()
    cookie_obj = MagicMock()
    cookie_obj.name = "cf_clearance"
    cookie_obj.value = "nodriver_cf_val"
    mock_tab.send = AsyncMock(return_value=MagicMock(cookies=[cookie_obj]))
    mock_tab.evaluate = AsyncMock(return_value="Mozilla/5.0 NodriverUA")

    result = await extract_clearance_cookies(mock_tab)

    assert result["cookies"]["cf_clearance"] == "nodriver_cf_val"
    assert result["user_agent"] == "Mozilla/5.0 NodriverUA"


@pytest.mark.asyncio
async def test_tls_async_client_from_browser_session() -> None:
    """TLSAsyncClient.from_browser_session настраивает заголовки и cookies из браузерной сессии."""
    mock_context = MagicMock()
    mock_context.cookies = AsyncMock(
        return_value=[
            {"name": "cf_clearance", "value": "bridge_cf_token"},
        ]
    )
    mock_page = MagicMock()
    mock_page.context = mock_context
    mock_page.evaluate = AsyncMock(return_value="Mozilla/5.0 CustomUA")

    client = await TLSAsyncClient.from_browser_session(
        mock_page, impersonate="chrome120", fallback_to_standard=True
    )
    assert client.impersonate == "chrome120"
    assert client.default_headers.get("User-Agent") == "Mozilla/5.0 CustomUA"
    assert "cf_clearance=bridge_cf_token" in client.default_headers.get("Cookie", "")


def test_tls_session_from_browser_session_selenium() -> None:
    """TLSSession.from_browser_session синхронно настраивает заголовки и cookies из Selenium."""
    mock_driver = MagicMock()
    # Удаляем атрибут context у Selenium мока чтобы не путать с Playwright
    del mock_driver.context
    mock_driver.get_cookies.return_value = [
        {"name": "cf_clearance", "value": "sync_cf_token"},
    ]
    mock_driver.execute_script.return_value = "Mozilla/5.0 SeleniumSync"

    session = TLSSession.from_browser_session(
        mock_driver, impersonate="chrome120", fallback_to_standard=True
    )
    assert session.impersonate == "chrome120"
    assert session.default_headers.get("User-Agent") == "Mozilla/5.0 SeleniumSync"
    assert "cf_clearance=sync_cf_token" in session.default_headers.get("Cookie", "")
