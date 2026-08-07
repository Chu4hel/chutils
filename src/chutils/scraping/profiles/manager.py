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
