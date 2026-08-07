"""Пакет адаптеров браузерных профилей."""

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

__all__ = [
    "export_nodriver_profile",
    "export_playwright_profile",
    "export_selenium_profile",
    "import_nodriver_profile",
    "import_playwright_profile",
    "import_selenium_profile",
]
