"""Адаптер экспорта и импорта профилей для Selenium / undetected-chromedriver."""

from typing import Any
from chutils.logger import setup_logger
from chutils.scraping.profiles.models import (
    BrowserProfile,
    CookieData,
    HeaderData,
    StorageData,
)

logger = setup_logger(__name__)


def export_selenium_profile(driver: Any) -> BrowserProfile:
    """Экспортировать профиль сессии из Selenium WebDriver.

    Args:
        driver: Объект selenium.webdriver.Chrome/Firefox.

    Returns:
        Экземпляр BrowserProfile.
    """
    raw_cookies = driver.get_cookies()
    cookies_list: list[CookieData] = []
    for c in raw_cookies:
        same_site_val = c.get("sameSite")
        same_site_normalized = None
        if same_site_val in ("Strict", "Lax", "None"):
            same_site_normalized = same_site_val

        cookies_list.append(
            CookieData(
                name=c.get("name", ""),
                value=c.get("value", ""),
                domain=c.get("domain", ""),
                path=c.get("path", "/"),
                expires=c.get("expiry"),
                http_only=c.get("httpOnly", False),
                secure=c.get("secure", False),
                same_site=same_site_normalized,
            )
        )

    user_agent = None
    try:
        user_agent = driver.execute_script("return navigator.userAgent;")
    except Exception as e:
        logger.debug("Не удалось получить userAgent из Selenium: %s", e)

    return BrowserProfile(
        engine_origin="selenium",
        cookies=cookies_list,
        storage=StorageData(),
        headers=HeaderData(user_agent=user_agent),
    )


def import_selenium_profile(driver: Any, profile: BrowserProfile) -> None:
    """Импортировать профиль сессии в Selenium WebDriver.

    Args:
        driver: Объект selenium.webdriver.
        profile: Экземпляр BrowserProfile.
    """
    for c in profile.cookies:
        cookie_dict: dict[str, Any] = {
            "name": c.name,
            "value": c.value,
            "domain": c.domain,
            "path": c.path,
        }
        if c.expires is not None:
            cookie_dict["expiry"] = int(c.expires)
        if c.http_only:
            cookie_dict["httpOnly"] = c.http_only
        if c.secure:
            cookie_dict["secure"] = c.secure
        if c.same_site:
            cookie_dict["sameSite"] = c.same_site

        try:
            driver.add_cookie(cookie_dict)
        except Exception as e:
            logger.warning("Не удалось добавить cookie '%s' в Selenium: %s", c.name, e)
