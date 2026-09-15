"""Интеграционные тесты ProfileManager."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from chutils.scraping import BrowserProfile, ProfileManager
from chutils.scraping.profiles.models import CookieData


@pytest.mark.asyncio
async def test_profile_manager_playwright():
    context_mock = AsyncMock()
    context_mock.storage_state.return_value = {
        "cookies": [
            {"name": "auth", "value": "secret", "domain": "test.com", "path": "/"}
        ],
        "origins": [],
    }

    profile = await ProfileManager.export_from_playwright(context_mock)
    assert isinstance(profile, BrowserProfile)
    assert profile.cookies[0].name == "auth"

    await ProfileManager.import_to_playwright(context_mock, profile)
    context_mock.add_cookies.assert_called_once()


@pytest.mark.asyncio
async def test_profile_manager_nodriver():
    tab_mock = AsyncMock()
    tab_mock.send.side_effect = [
        {
            "cookies": [
                {"name": "nd", "value": "val", "domain": "test.com", "path": "/"}
            ]
        },
        None,
        None,
    ]
    tab_mock.evaluate.return_value = "UA"

    profile = await ProfileManager.export_from_nodriver(tab_mock)
    assert isinstance(profile, BrowserProfile)
    assert profile.cookies[0].name == "nd"

    await ProfileManager.import_to_nodriver(tab_mock, profile)
    assert tab_mock.send.call_count >= 2


def test_profile_manager_selenium():
    driver_mock = MagicMock()
    driver_mock.get_cookies.return_value = [
        {"name": "sel", "value": "val", "domain": "test.com", "path": "/"}
    ]
    driver_mock.execute_script.return_value = "UA"

    profile = ProfileManager.export_from_selenium(driver_mock)
    assert isinstance(profile, BrowserProfile)
    assert profile.cookies[0].name == "sel"

    ProfileManager.import_to_selenium(driver_mock, profile)
    driver_mock.add_cookie.assert_called_once()


def test_profile_manager_save_and_load(tmp_path):
    profile = BrowserProfile(
        engine_origin="playwright",
        cookies=[CookieData(name="k", value="v", domain="d.com")],
    )

    file_path = tmp_path / "pm_test.chprofile"
    saved = ProfileManager.save(profile, file_path, password="pass")
    assert saved.exists()

    loaded = ProfileManager.load(saved, password="pass")
    assert loaded.engine_origin == "playwright"
    assert loaded.cookies[0].value == "v"


@pytest.mark.asyncio
async def test_save_profile_after_warmup(tmp_path):
    # 1. Playwright
    page_mock = MagicMock()
    context_mock = AsyncMock()
    page_mock.context = context_mock
    context_mock.storage_state.return_value = {
        "cookies": [
            {"name": "pw_warm", "value": "1", "domain": "example.com", "path": "/"}
        ],
        "origins": [],
    }

    pw_path = tmp_path / "pw_warm.chprofile"
    saved_pw = await ProfileManager.save_profile_after_warmup(
        page_mock, pw_path, metadata={"tag": "warmed_playwright"}
    )
    assert saved_pw.metadata["warmed_up"] == "true"
    assert saved_pw.metadata["tag"] == "warmed_playwright"
    assert pw_path.exists()

    # 2. Selenium
    driver_mock = MagicMock()
    driver_mock.get_cookies.return_value = [
        {"name": "sel_warm", "value": "2", "domain": "example.com", "path": "/"}
    ]
    driver_mock.execute_script.return_value = "Chrome UA"

    sel_path = tmp_path / "sel_warm.chprofile"
    saved_sel = await ProfileManager.save_profile_after_warmup(
        driver_mock, sel_path, metadata={"tag": "warmed_selenium"}
    )
    assert saved_sel.metadata["warmed_up"] == "true"
    assert saved_sel.metadata["tag"] == "warmed_selenium"
    assert sel_path.exists()
