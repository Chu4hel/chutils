"""Тесты сохранения, воспроизведения оффлайн-снапшотов страниц и фикстур."""

import asyncio
from pathlib import Path

import pytest

from chutils.scraping.testing.mocks import (
    MockNodriverTab,
    MockPlaywrightPage,
    MockSeleniumDriver,
)
from chutils.scraping.testing.snapshot import SnapshotRecorder, use_html_snapshot


def test_snapshot_recorder_basic(tmp_path: Path) -> None:
    """Проверяет базовое сохранение, проверку наличия и загрузку снапшотов."""
    recorder = SnapshotRecorder(snapshot_dir=tmp_path)

    assert not recorder.exists("page_one")

    saved_path = recorder.save("page_one", "<h1>Title 1</h1>")
    assert saved_path.exists()
    assert recorder.exists("page_one")

    loaded_html = recorder.load("page_one")
    assert loaded_html == "<h1>Title 1</h1>"

    with pytest.raises(FileNotFoundError):
        recorder.load("unknown_page")


def test_use_html_snapshot_context_manager(tmp_path: Path) -> None:
    """Проверяет использование use_html_snapshot как контекстного менеджера с моками."""
    recorder = SnapshotRecorder(snapshot_dir=tmp_path)
    sample_html = "<div class='item'>Товар</div>"
    recorder.save("sample", sample_html)

    # 1. Сырой HTML
    with use_html_snapshot("sample", snapshot_dir=tmp_path) as content:
        assert content == sample_html

    # 2. Mock nodriver
    with use_html_snapshot("sample", snapshot_dir=tmp_path, as_mock="nodriver") as tab:
        assert isinstance(tab, MockNodriverTab)

    # 3. Mock Playwright
    with use_html_snapshot(
        "sample", snapshot_dir=tmp_path, as_mock="playwright"
    ) as page:
        assert isinstance(page, MockPlaywrightPage)

    # 4. Mock Selenium
    with use_html_snapshot(
        "sample", snapshot_dir=tmp_path, as_mock="selenium"
    ) as driver:
        assert isinstance(driver, MockSeleniumDriver)


def test_use_html_snapshot_with_fetcher(tmp_path: Path) -> None:
    """Проверяет автоматическую запись через fetcher при отсутствии снапшота."""
    called = False

    def fetch_page() -> str:
        nonlocal called
        called = True
        return "<span>Dynamic Data</span>"

    # При первом вызове снапшота нет, вызывается fetcher и сохраняет
    with use_html_snapshot(
        "dynamic_card", snapshot_dir=tmp_path, fetcher=fetch_page
    ) as html:
        assert html == "<span>Dynamic Data</span>"
        assert called

    # При повторном вызове fetcher не должен вызываться
    called = False
    with use_html_snapshot(
        "dynamic_card", snapshot_dir=tmp_path, fetcher=fetch_page
    ) as html:
        assert html == "<span>Dynamic Data</span>"
        assert not called


@pytest.mark.asyncio
async def test_use_html_snapshot_async_fetcher(tmp_path: Path) -> None:
    """Проверяет асинхронный fetcher при отсутствии снапшота."""

    async def async_fetch() -> str:
        await asyncio.sleep(0.01)
        return "<p>Async Page</p>"

    async with use_html_snapshot(
        "async_card", snapshot_dir=tmp_path, fetcher=async_fetch
    ) as html:
        assert html == "<p>Async Page</p>"

    # Проверяем, что файл сохранен
    assert (tmp_path / "async_card.html").exists()


@pytest.mark.asyncio
async def test_use_html_snapshot_as_decorator(tmp_path: Path) -> None:
    """Проверяет применение use_html_snapshot в качестве декоратора тестовых функций."""
    recorder = SnapshotRecorder(snapshot_dir=tmp_path)
    recorder.save("catalog_page", "<ul><li>A</li><li>B</li></ul>")

    @use_html_snapshot("catalog_page", snapshot_dir=tmp_path, as_mock="playwright")
    async def sample_test(page: MockPlaywrightPage) -> None:
        items = await page.locator("li").all()
        assert len(items) == 2

    await sample_test()
