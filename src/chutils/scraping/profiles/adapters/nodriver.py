"""Адаптер экспорта и импорта профилей для nodriver (CDP)."""

from typing import Any
from chutils.logger import setup_logger
from chutils.scraping.profiles.models import (
    BrowserProfile,
    CookieData,
    HeaderData,
    StorageData,
)

logger = setup_logger(__name__)


async def export_nodriver_profile(tab: Any) -> BrowserProfile:
    """Экспортировать профиль сессии из вкладки nodriver Tab через CDP.

    Args:
        tab: Объект nodriver.Tab.

    Returns:
        Экземпляр BrowserProfile.
    """
    raw_cookies = await tab.send("Network.getAllCookies")
    cookies_list: list[CookieData] = []
    if isinstance(raw_cookies, dict) and "cookies" in raw_cookies:
        for c in raw_cookies["cookies"]:
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
                    expires=c.get("expires"),
                    http_only=c.get("httpOnly", False),
                    secure=c.get("secure", False),
                    same_site=same_site_normalized,
                )
            )

    # Извлечение User-Agent
    user_agent = None
    try:
        eval_res = await tab.evaluate("navigator.userAgent")
        if isinstance(eval_res, str):
            user_agent = eval_res
    except Exception as e:
        logger.debug("Не удалось получить userAgent из nodriver: %s", e)

    return BrowserProfile(
        engine_origin="nodriver",
        cookies=cookies_list,
        storage=StorageData(),
        headers=HeaderData(user_agent=user_agent),
    )


async def import_nodriver_profile(tab: Any, profile: BrowserProfile) -> None:
    """Импортировать профиль сессии во вкладку nodriver Tab через CDP.

    Args:
        tab: Объект nodriver.Tab.
        profile: Экземпляр BrowserProfile.
    """
    if profile.cookies:
        cdp_cookies = []
        for c in profile.cookies:
            cookie_dict: dict[str, Any] = {
                "name": c.name,
                "value": c.value,
                "domain": c.domain,
                "path": c.path,
            }
            if c.expires is not None:
                cookie_dict["expires"] = c.expires
            if c.http_only:
                cookie_dict["httpOnly"] = c.http_only
            if c.secure:
                cookie_dict["secure"] = c.secure
            if c.same_site:
                cookie_dict["sameSite"] = c.same_site
            cdp_cookies.append(cookie_dict)

        await tab.send("Network.setCookies", {"cookies": cdp_cookies})

    if profile.headers.user_agent:
        try:
            await tab.send(
                "Network.setUserAgentOverride",
                {"userAgent": profile.headers.user_agent},
            )
        except Exception as e:
            logger.warning("Не удалось установить User-Agent в nodriver: %s", e)
