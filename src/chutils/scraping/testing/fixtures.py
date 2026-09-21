"""
Pytest плагин и фикстуры для автотестирования парсеров и скраперов.

Автоматически регистрируется pytest через entry_point `pytest11`
и предоставляет готовые фикстуры для мок- и live-тестирования.
Все тяжелые зависимости импортируются лениво внутри фикстур.
"""

from __future__ import annotations

from collections.abc import Callable, Generator
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from chutils.scraping.testing.mocks import (
        MockNodriverTab,
        MockPlaywrightPage,
        MockSeleniumDriver,
    )
    from chutils.scraping.testing.server import LocalTestServer
    from chutils.scraping.testing.session import LiveBrowserSession
    from chutils.scraping.testing.snapshot import SnapshotRecorder


def pytest_configure(config: Any) -> None:
    """Регистрирует кастомные маркеры chutils для pytest.

    Args:
        config: Объект конфигурации pytest.
    """
    config.addinivalue_line(
        "markers",
        "live_scraping: маркер для интеграционных тестов со сквозным запуском реального браузера",
    )


@pytest.fixture
def local_test_server() -> Generator[LocalTestServer, None, None]:
    """Предоставляет запущенный локальный тестовый HTTP-сервер песочницы.

    Yields:
        Запущенный экземпляр LocalTestServer.
    """
    from chutils.scraping.testing.server import LocalTestServer

    with LocalTestServer() as server:
        yield server


@pytest.fixture
def live_browser_session() -> Generator[LiveBrowserSession, None, None]:
    """Предоставляет сессию реального браузера с гарантированным teardown зомби-процессов.

    Yields:
        Активный экземпляр LiveBrowserSession.
    """
    from chutils.scraping.testing.session import LiveBrowserSession

    with LiveBrowserSession() as session:
        yield session


@pytest.fixture
def html_snapshot_recorder(tmp_path: Path) -> SnapshotRecorder:
    """Предоставляет менеджер снапшотов SnapshotRecorder во временном каталоге.

    Args:
        tmp_path: Временная папка теста от pytest.

    Returns:
        Экземпляр SnapshotRecorder.
    """
    from chutils.scraping.testing.snapshot import SnapshotRecorder

    return SnapshotRecorder(snapshot_dir=tmp_path)


@pytest.fixture
def mock_nodriver_tab() -> Callable[..., MockNodriverTab]:
    """Фабрика для создания легковесного мока вкладки nodriver.

    Returns:
        Функция, принимающая HTML строку и возвращающая MockNodriverTab.
    """

    def _factory(html: str = "") -> MockNodriverTab:
        from chutils.scraping.testing.mocks import MockNodriverTab

        return MockNodriverTab(html)

    return _factory


@pytest.fixture
def mock_playwright_page() -> Callable[..., MockPlaywrightPage]:
    """Фабрика для создания мока страницы Playwright.

    Returns:
        Функция, принимающая HTML строку и возвращающая MockPlaywrightPage.
    """

    def _factory(html: str = "") -> MockPlaywrightPage:
        from chutils.scraping.testing.mocks import MockPlaywrightPage

        return MockPlaywrightPage(html)

    return _factory


@pytest.fixture
def mock_selenium_driver() -> Callable[..., MockSeleniumDriver]:
    """Фабрика для создания мока драйвера Selenium.

    Returns:
        Функция, принимающая HTML строку и возвращающая MockSeleniumDriver.
    """

    def _factory(html: str = "") -> MockSeleniumDriver:
        from chutils.scraping.testing.mocks import MockSeleniumDriver

        return MockSeleniumDriver(html)

    return _factory
