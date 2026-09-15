"""Тесты легковесных моков браузерных страниц (nodriver, Playwright, Selenium)."""

import pytest

from chutils.scraping.testing.mocks import (
    MockNodriverTab,
    MockPlaywrightPage,
    MockSeleniumDriver,
)

SAMPLE_HTML = """
<!DOCTYPE html>
<html>
<head><title>Test Store</title></head>
<body>
    <h1 id="header">Catalog of Products</h1>
    <div class="container">
        <div class="product-card" data-id="101">
            <h2 class="title">Product Alpha</h2>
            <span class="price">$19.99</span>
            <a href="/items/101" class="btn buy-btn">Buy Now</a>
        </div>
        <div class="product-card" data-id="102">
            <h2 class="title">Product Beta</h2>
            <span class="price">$29.99</span>
            <a href="/items/102" class="btn buy-btn">Buy Now</a>
        </div>
    </div>
    <footer>Contact us at support@example.com</footer>
</body>
</html>
"""


@pytest.mark.asyncio
async def test_mock_nodriver_tab() -> None:
    """Проверяет эмуляцию nodriver.Tab и nodriver.Element."""
    tab = MockNodriverTab(SAMPLE_HTML)

    # 1. Проверка получения контента
    content = await tab.get_content()
    assert "Catalog of Products" in content

    # 2. Выборка единичного элемента по id и тегу
    h1 = await tab.select("#header")
    assert h1 is not None
    assert h1.text == "Catalog of Products"

    # 3. Выборка нескольких элементов
    cards = await tab.select_all(".product-card")
    assert len(cards) == 2

    first_card = cards[0]
    assert first_card.attrs.get("data-id") == "101"

    # 4. Вложенная выборка внутри элемента
    title_elem = await first_card.select(".title")
    assert title_elem is not None
    assert title_elem.text == "Product Alpha"

    price_elem = await first_card.select(".price")
    assert price_elem is not None
    assert price_elem.text == "$19.99"

    # 5. Поиск по тексту (find)
    beta = await tab.find("Product Beta")
    assert beta is not None
    assert beta.text == "Product Beta"

    # 6. evaluate эмуляция
    eval_res = await tab.evaluate("document.title")
    assert eval_res == "Test Store"


@pytest.mark.asyncio
async def test_mock_playwright_page() -> None:
    """Проверяет эмуляцию playwright.Page и Locator."""
    page = MockPlaywrightPage(SAMPLE_HTML)

    assert await page.title() == "Test Store"
    assert "Catalog of Products" in (await page.content())

    # 1. Locator и подсчет
    locator = page.locator(".product-card")
    assert await locator.count() == 2

    # 2. Итерация через .all()
    items = await locator.all()
    assert len(items) == 2

    first_item = items[0]
    assert await first_item.locator(".title").inner_text() == "Product Alpha"
    assert await first_item.locator(".price").inner_text() == "$19.99"
    assert await first_item.locator("a").get_attribute("href") == "/items/101"

    # 3. First, Last, Nth
    assert await locator.first.locator(".title").inner_text() == "Product Alpha"
    assert await locator.last.locator(".title").inner_text() == "Product Beta"
    assert await locator.nth(1).locator(".title").inner_text() == "Product Beta"


def test_mock_selenium_driver() -> None:
    """Проверяет эмуляцию Selenium WebDriver и WebElement."""
    driver = MockSeleniumDriver(SAMPLE_HTML)

    assert driver.title == "Test Store"
    assert "Catalog of Products" in driver.page_source

    # 1. Поиск по CSS селектору
    header = driver.find_element("css selector", "#header")
    assert header.text == "Catalog of Products"

    # 2. Поиск списка элементов
    cards = driver.find_elements("css selector", ".product-card")
    assert len(cards) == 2

    # 3. Вложенный поиск
    first_card = cards[0]
    title = first_card.find_element("css selector", ".title")
    assert title.text == "Product Alpha"
    assert first_card.get_attribute("data-id") == "101"

    link = first_card.find_element("css selector", "a.buy-btn")
    assert link.get_attribute("href") == "/items/101"
