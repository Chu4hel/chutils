"""Моки страниц браузеров для автономного тестирования скраперов."""

from chutils.scraping.testing.mocks.dom import DOMNode, parse_html_dom
from chutils.scraping.testing.mocks.nodriver import (
    MockNodriverElement,
    MockNodriverTab,
)
from chutils.scraping.testing.mocks.playwright import (
    MockPlaywrightLocator,
    MockPlaywrightPage,
)
from chutils.scraping.testing.mocks.selenium import (
    MockSeleniumDriver,
    MockSeleniumElement,
)

__all__ = [
    "DOMNode",
    "MockNodriverElement",
    "MockNodriverTab",
    "MockPlaywrightLocator",
    "MockPlaywrightPage",
    "MockSeleniumDriver",
    "MockSeleniumElement",
    "parse_html_dom",
]
