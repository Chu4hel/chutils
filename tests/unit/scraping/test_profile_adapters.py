"""Тесты адаптеров профилей браузеров (nodriver, playwright, selenium)."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from chutils.scraping.profiles.adapters.nodriver import (
    export_nodriver_profile,
    import_nodriver_profile,
)
from chutils.scraping.profiles.adapters.playwright import (
    export_playwright_profile,
    import_playwright_profile,
)
from chutils.scraping.profiles.adapters.selenium import (
    export_selenium_profile,
    import_selenium_profile,
)
from chutils.scraping.profiles.models import BrowserProfile, CookieData, HeaderData, StorageData


@pytest.mark.asyncio
async def test_playwright_adapter():
    context_mock = AsyncMock()
    context_mock.storage_state.return_value = {
        "cookies": [
            {
                "name": "pw_token",
                "value": "12345",
                "domain": "example.org",
                "path": "/",
                "expires": 1700000000,
                "httpOnly": True,
                "secure": True,
                "sameSite": "Lax",
            }
        ],
        "origins": [
            {
                "origin": "https://example.org",
                "localStorage": [{"name": "key", "value": "val"}],
            }
        ],
    }

    profile = await export_playwright_profile(context_mock)
    assert profile.engine_origin == "playwright"
    assert len(profile.cookies) == 1
    assert profile.cookies[0].name == "pw_token"
    assert profile.storage.local_storage["https://example.org"]["key"] == "val"

    # Импорт
    await import_playwright_profile(context_mock, profile)
    context_mock.add_cookies.assert_called_once()


@pytest.mark.asyncio
async def test_nodriver_adapter():
    tab_mock = AsyncMock()
    tab_mock.send.side_effect = [
        {
            "cookies": [
                {
                    "name": "nd_cookie",
                    "value": "abc",
                    "domain": "nodriver.dev",
                    "path": "/",
                    "sameSite": "Strict",
                }
            ]
        },
        None,  # for Network.setCookies
        None,  # for Network.setUserAgentOverride
    ]
    tab_mock.evaluate.return_value = "Mozilla/5.0 Nodriver"

    profile = await export_nodriver_profile(tab_mock)
    assert profile.engine_origin == "nodriver"
    assert len(profile.cookies) == 1
    assert profile.cookies[0].name == "nd_cookie"
    assert profile.headers.user_agent == "Mozilla/5.0 Nodriver"

    await import_nodriver_profile(tab_mock, profile)
    assert tab_mock.send.call_count >= 2


def test_selenium_adapter():
    driver_mock = MagicMock()
    driver_mock.get_cookies.return_value = [
        {
            "name": "sel_cookie",
            "value": "sel_val",
            "domain": "selenium.dev",
            "path": "/",
            "expiry": 1800000000,
            "httpOnly": False,
            "secure": True,
            "sameSite": "Lax",
        }
    ]
    driver_mock.execute_script.return_value = "Mozilla/5.0 Selenium"

    profile = export_selenium_profile(driver_mock)
    assert profile.engine_origin == "selenium"
    assert len(profile.cookies) == 1
    assert profile.cookies[0].name == "sel_cookie"
    assert profile.headers.user_agent == "Mozilla/5.0 Selenium"

    import_selenium_profile(driver_mock, profile)
    driver_mock.add_cookie.assert_called_once()
