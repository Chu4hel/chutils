"""Тесты адаптеров профилей браузеров (nodriver, playwright, selenium)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

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


@pytest.mark.asyncio
async def test_nodriver_adapter_cdp_cookie_objects():
    """Проверяет экспорт, когда send возвращает список объектов cdp.network.Cookie с enum same_site."""
    class FakeSameSiteEnum:
        value = "Lax"

    class FakeCDPCookie:
        def __init__(self):
            self.name = "cdp_token"
            self.value = "secret_xyz"
            self.domain = "target.com"
            self.path = "/api"
            self.expires = 1700000000.0
            self.http_only = True
            self.secure = True
            self.same_site = FakeSameSiteEnum()

    tab_mock = AsyncMock()
    tab_mock.send.return_value = [FakeCDPCookie()]
    tab_mock.evaluate.return_value = "Mozilla/5.0 Nodriver"

    profile = await export_nodriver_profile(tab_mock)
    assert len(profile.cookies) == 1
    cookie = profile.cookies[0]
    assert cookie.name == "cdp_token"
    assert cookie.value == "secret_xyz"
    assert cookie.domain == "target.com"
    assert cookie.path == "/api"
    assert cookie.expires == 1700000000.0
    assert cookie.http_only is True
    assert cookie.secure is True
    assert cookie.same_site == "Lax"


@pytest.mark.asyncio
async def test_nodriver_adapter_wrapped_result_and_direct_list():
    """Проверяет экспорт, когда send возвращает объект с атрибутом .cookies или список словарей."""
    # 1. Объект с атрибутом .cookies
    class FakeCDPResult:
        def __init__(self, cookies):
            self.cookies = cookies

    tab_mock = AsyncMock()
    tab_mock.send.return_value = FakeCDPResult(
        cookies=[
            {
                "name": "wrapped_cookie",
                "value": "val1",
                "domain": ".site.org",
                "sameSite": "Strict",
            }
        ]
    )
    tab_mock.evaluate.return_value = None

    profile = await export_nodriver_profile(tab_mock)
    assert len(profile.cookies) == 1
    assert profile.cookies[0].name == "wrapped_cookie"
    assert profile.cookies[0].same_site == "Strict"

    # 2. Прямой список словарей
    tab_mock.send.return_value = [
        {
            "name": "direct_list_cookie",
            "value": "val2",
            "domain": "site2.org",
        }
    ]
    profile2 = await export_nodriver_profile(tab_mock)
    assert len(profile2.cookies) == 1
    assert profile2.cookies[0].name == "direct_list_cookie"
    assert profile2.cookies[0].value == "val2"


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
