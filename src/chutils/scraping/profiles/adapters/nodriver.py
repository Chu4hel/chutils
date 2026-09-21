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


def _extract_cookie_field(c: Any, *keys: str, default: Any = None) -> Any:
    """Безопасно извлекает значение поля из словаря или CDP-объекта Cookie."""
    if isinstance(c, dict):
        for k in keys:
            if k in c and c[k] is not None:
                return c[k]
        return default
    for k in keys:
        if hasattr(c, k):
            val = getattr(c, k)
            if val is not None:
                return getattr(val, "value", val)
    return default


async def export_nodriver_profile(tab: Any) -> BrowserProfile:
    """Экспортировать профиль сессии из вкладки nodriver Tab через CDP.

    Args:
        tab: Объект nodriver.Tab.

    Returns:
        Экземпляр BrowserProfile.
    """
    raw_cookies = None
    try:
        raw_cookies = await tab.send("Network.getAllCookies")
    except Exception:
        try:
            from nodriver.cdp import network

            raw_cookies = await tab.send(network.get_all_cookies())
        except Exception:
            try:
                from nodriver.cdp import network

                raw_cookies = await tab.send(network.get_cookies())
            except Exception as e:
                logger.debug("Не удалось получить куки через CDP: %s", e)

    raw_list: list[Any] = []
    if isinstance(raw_cookies, list):
        raw_list = raw_cookies
    elif isinstance(raw_cookies, dict):
        raw_list = raw_cookies.get("cookies", [])
    elif hasattr(raw_cookies, "cookies"):
        cookies_attr = getattr(raw_cookies, "cookies")
        if isinstance(cookies_attr, list):
            raw_list = cookies_attr

    cookies_list: list[CookieData] = []
    for c in raw_list:
        name = _extract_cookie_field(c, "name", default="")
        if not name:
            continue
        value = _extract_cookie_field(c, "value", default="")
        domain = _extract_cookie_field(c, "domain", default="")
        path = _extract_cookie_field(c, "path", default="/")
        expires = _extract_cookie_field(c, "expires", "expiry", default=None)
        http_only = bool(_extract_cookie_field(c, "httpOnly", "http_only", default=False))
        secure = bool(_extract_cookie_field(c, "secure", default=False))

        raw_same_site = _extract_cookie_field(c, "sameSite", "same_site", default=None)
        same_site_normalized = None
        if raw_same_site is not None:
            val_str = str(getattr(raw_same_site, "value", raw_same_site)).capitalize()
            if val_str in ("Strict", "Lax", "None"):
                same_site_normalized = val_str

        cookies_list.append(
            CookieData(
                name=str(name),
                value=str(value),
                domain=str(domain),
                path=str(path),
                expires=float(expires) if expires is not None else None,
                http_only=http_only,
                secure=secure,
                same_site=same_site_normalized,  # type: ignore[arg-type]
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
