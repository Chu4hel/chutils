"""Адаптер экспорта и импорта профилей для Playwright."""

from typing import Any
from chutils.exceptions import OptionalDependencyError
from chutils.logger import setup_logger
from chutils.scraping.profiles.models import (
    BrowserProfile,
    CookieData,
    HeaderData,
    StorageData,
)

logger = setup_logger(__name__)


async def export_playwright_profile(context: Any) -> BrowserProfile:
    """Экспортировать профиль сессии из Playwright BrowserContext.

    Args:
        context: Объект playwright.async_api.BrowserContext.

    Returns:
        Экземпляр BrowserProfile.
    """
    try:
        storage_state = await context.storage_state()
    except AttributeError:
        raise OptionalDependencyError("Переданный объект не является Playwright BrowserContext")

    cookies_list: list[CookieData] = []
    for c in storage_state.get("cookies", []):
        cookies_list.append(
            CookieData(
                name=c.get("name", ""),
                value=c.get("value", ""),
                domain=c.get("domain", ""),
                path=c.get("path", "/"),
                expires=c.get("expires"),
                http_only=c.get("httpOnly", False),
                secure=c.get("secure", False),
                same_site=c.get("sameSite"),
            )
        )

    local_storage: dict[str, dict[str, str]] = {}
    for origin_entry in storage_state.get("origins", []):
        origin = origin_entry.get("origin", "")
        ls_dict: dict[str, str] = {}
        for item in origin_entry.get("localStorage", []):
            ls_dict[item["name"]] = item["value"]
        if ls_dict:
            local_storage[origin] = ls_dict

    return BrowserProfile(
        engine_origin="playwright",
        cookies=cookies_list,
        storage=StorageData(local_storage=local_storage),
        headers=HeaderData(),
    )


async def import_playwright_profile(context: Any, profile: BrowserProfile) -> None:
    """Импортировать профиль сессии в Playwright BrowserContext.

    Args:
        context: Объект playwright.async_api.BrowserContext.
        profile: Экземпляр BrowserProfile.
    """
    pw_cookies = []
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
        pw_cookies.append(cookie_dict)

    if pw_cookies:
        await context.add_cookies(pw_cookies)

    # Восстановление LocalStorage для страниц
    if profile.storage.local_storage:
        for origin, items in profile.storage.local_storage.items():
            page = await context.new_page()
            try:
                await page.goto(origin)
                for k, v in items.items():
                    await page.evaluate(
                        "(args) => localStorage.setItem(args.key, args.val)",
                        {"key": k, "val": v},
                    )
            except Exception as e:
                logger.warning("Не удалось применить localStorage для origin %s: %s", origin, e)
            finally:
                await page.close()
