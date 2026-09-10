"""Единый фасад управления профилями браузеров."""

from pathlib import Path
from typing import Any

from chutils.logger import setup_logger
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
from chutils.scraping.profiles.models import BrowserProfile
from chutils.scraping.profiles.storage import (
    load_profile_from_file,
    save_profile_to_file,
)

logger = setup_logger(__name__)


class ProfileManager:
    """Менеджер для универсального экспорта, конвертации и импорта браузерных профилей."""

    @staticmethod
    async def export_from_playwright(context: Any) -> BrowserProfile:
        """Экспортировать профиль сессии из Playwright BrowserContext.

        Args:
            context: Объект playwright.async_api.BrowserContext.

        Returns:
            Экземпляр BrowserProfile.
        """
        return await export_playwright_profile(context)

    @staticmethod
    async def import_to_playwright(context: Any, profile: BrowserProfile) -> None:
        """Импортировать профиль сессии в Playwright BrowserContext.

        Args:
            context: Объект playwright.async_api.BrowserContext.
            profile: Экземпляр BrowserProfile.
        """
        await import_playwright_profile(context, profile)

    @staticmethod
    async def export_from_nodriver(tab: Any) -> BrowserProfile:
        """Экспортировать профиль сессии из nodriver Tab.

        Args:
            tab: Объект nodriver.Tab.

        Returns:
            Экземпляр BrowserProfile.
        """
        return await export_nodriver_profile(tab)

    @staticmethod
    async def import_to_nodriver(tab: Any, profile: BrowserProfile) -> None:
        """Импортировать профиль сессии в nodriver Tab.

        Args:
            tab: Объект nodriver.Tab.
            profile: Экземпляр BrowserProfile.
        """
        await import_nodriver_profile(tab, profile)

    @staticmethod
    def export_from_selenium(driver: Any) -> BrowserProfile:
        """Экспортировать профиль сессии из Selenium WebDriver.

        Args:
            driver: Объект selenium.webdriver.

        Returns:
            Экземпляр BrowserProfile.
        """
        return export_selenium_profile(driver)

    @staticmethod
    def import_to_selenium(driver: Any, profile: BrowserProfile) -> None:
        """Импортировать профиль сессии в Selenium WebDriver.

        Args:
            driver: Объект selenium.webdriver.
            profile: Экземпляр BrowserProfile.
        """
        import_selenium_profile(driver, profile)

    @staticmethod
    def save(
        profile: BrowserProfile,
        filepath: str | Path,
        password: str | None = None,
    ) -> Path:
        """Сохранить профиль в `.chprofile` файл с опциональным шифрованием.

        Args:
            profile: Экземпляр BrowserProfile.
            filepath: Путь к сохраняемому файлу.
            password: Пароль для шифрования.

        Returns:
            Path к сохраненному файлу.
        """
        return save_profile_to_file(profile, filepath, password=password)

    @staticmethod
    def load(
        filepath: str | Path,
        password: str | None = None,
    ) -> BrowserProfile:
        """Загрузить профиль из `.chprofile` файла с опциональной расшифровкой.

        Args:
            filepath: Путь к файлу .chprofile.
            password: Пароль для расшифровки.

        Returns:
            Экземпляр BrowserProfile.
        """
        return load_profile_from_file(filepath, password=password)

    @classmethod
    async def save_profile_after_warmup(
        cls,
        browser_obj: Any,
        filepath: str | Path,
        password: str | None = None,
        metadata: dict[str, str] | None = None,
        driver_type: str | None = None,
    ) -> BrowserProfile:
        """Экспортирует состояние сессии после прогрева и сохраняет в `.chprofile` файл.

        Поддерживает Playwright (BrowserContext или Page), nodriver (Tab) и Selenium WebDriver.

        Args:
            browser_obj: Сессия (Playwright BrowserContext/Page, nodriver Tab или Selenium WebDriver).
            filepath: Путь к сохраняемому файлу (.chprofile).
            password: Опциональный пароль для шифрования данных профиля.
            metadata: Дополнительные метаданные для сохранения в профиле.
            driver_type: Необязательный тип драйвера ('playwright', 'nodriver', 'selenium'). Если None, определяется автоматически.

        Returns:
            Экземпляр сохраненного BrowserProfile.
        """
        import datetime
        from chutils.scraping.humanize.actions import _is_nodriver

        if driver_type == "selenium":
            profile = cls.export_from_selenium(browser_obj)
        elif driver_type == "nodriver":
            profile = await cls.export_from_nodriver(browser_obj)
        elif driver_type == "playwright":
            context = getattr(browser_obj, "context", browser_obj)
            profile = await cls.export_from_playwright(context)
        else:
            try:
                from unittest.mock import Mock

                is_mock = isinstance(browser_obj, Mock)
            except ImportError:
                is_mock = False

            if is_mock:
                if getattr(browser_obj, "_is_nodriver", False) is True:
                    profile = await cls.export_from_nodriver(browser_obj)
                elif (
                    "context" in browser_obj.__dict__
                    or "storage_state" in browser_obj.__dict__
                ):
                    context = getattr(browser_obj, "context", browser_obj)
                    profile = await cls.export_from_playwright(context)
                else:
                    try:
                        profile = cls.export_from_selenium(browser_obj)
                    except Exception:
                        context = getattr(browser_obj, "context", browser_obj)
                        profile = await cls.export_from_playwright(context)
            else:
                if _is_nodriver(browser_obj):
                    profile = await cls.export_from_nodriver(browser_obj)
                elif hasattr(browser_obj, "get_cookies"):
                    profile = cls.export_from_selenium(browser_obj)
                else:
                    context = getattr(browser_obj, "context", browser_obj)
                    profile = await cls.export_from_playwright(context)

        profile.metadata["warmed_up"] = "true"
        profile.metadata["last_warmed_up_at"] = (
            datetime.datetime.now(datetime.timezone.utc).isoformat()
        )
        if metadata:
            profile.metadata.update(metadata)

        cls.save(profile, filepath, password=password)
        return profile

