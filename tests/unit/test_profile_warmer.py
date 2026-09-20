import importlib.util
import sys
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_mock import MockerFixture

# Мокаем библиотеки
mock_playwright = MagicMock()
mock_selenium = MagicMock()
mock_nodriver = MagicMock()
mock_cdp = MagicMock(spec=["input_"])
mock_input = MagicMock()
mock_cdp.input_ = mock_input


@pytest.fixture(autouse=True)
def mock_sys_modules(mocker: MockerFixture) -> None:
    """Мокает библиотеки на уровне sys.modules только на время тестов в этом файле."""
    mocker.patch.dict(
        sys.modules,
        {
            "playwright": mock_playwright,
            "selenium": mock_selenium,
            "nodriver": mock_nodriver,
            "nodriver.cdp": mock_cdp,
            "nodriver.cdp.input_": mock_input,
        },
    )


@pytest.fixture(autouse=True)
def mock_find_specs(mocker: MockerFixture) -> None:
    """Глушит проверку наличия всех библиотек, возвращая фиктивные specs."""
    orig_find_spec = importlib.util.find_spec

    def custom_find_spec(name: str, package: str | None = None) -> Any:
        if name in ("playwright", "selenium", "nodriver"):
            mock_spec = MagicMock()
            mock_spec.__spec__ = MagicMock()
            return mock_spec
        return orig_find_spec(name, package)

    mocker.patch("importlib.util.find_spec", side_effect=custom_find_spec)


def get_warmers():
    import chutils.scraping.humanize.warmer as warmer_mod

    return warmer_mod.ProfileWarmer, warmer_mod.SyncProfileWarmer


@pytest.mark.asyncio
async def test_profile_warmer_playwright() -> None:
    """Тестирует ProfileWarmer с Playwright Page."""
    page = MagicMock()
    page.goto = AsyncMock()
    page.url = "https://example.com"
    # Имитируем возврат текущего URL и списка внутренних ссылок
    page.evaluate = AsyncMock(
        side_effect=lambda js, *args: (
            "https://example.com"
            if "window.location.href" in js
            else ["/about", "/contact"]
        )
    )

    mock_element = AsyncMock()
    page.query_selector_all = AsyncMock(return_value=[mock_element])

    # Патчим функции мыши, скролла и выбор действия, чтобы избежать реальных задержек и сделать тест детерминированным
    with (
        patch("chutils.scraping.humanize.warmer.async_move_mouse", AsyncMock()),
        patch("chutils.scraping.humanize.warmer.async_scroll_to", AsyncMock()),
        patch("chutils.scraping.humanize.warmer.async_human_sleep", AsyncMock()),
        patch("random.choice", return_value="click_link"),
    ):
        ProfileWarmer, _ = get_warmers()
        warmer = ProfileWarmer(page)
        await warmer.warm_up(
            sites=["https://example.com"],
            sites_count=1,
            duration_per_site=(0.01, 0.02),
            click_random_links=True,
        )

        page.goto.assert_any_call("https://example.com")
        assert page.evaluate.call_count > 0


@pytest.mark.asyncio
async def test_profile_warmer_nodriver() -> None:
    """Тестирует ProfileWarmer с nodriver Tab."""
    tab = AsyncMock()
    tab._is_nodriver = True
    tab.get = AsyncMock()
    tab.url = "https://example.com"
    tab.evaluate = AsyncMock(
        side_effect=lambda js, *args: (
            "https://example.com"
            if "window.location.href" in js
            else ["/about", "/contact"]
        )
    )

    with (
        patch("chutils.scraping.humanize.warmer.async_move_mouse", AsyncMock()),
        patch("chutils.scraping.humanize.warmer.async_scroll_to", AsyncMock()),
        patch("chutils.scraping.humanize.warmer.async_human_sleep", AsyncMock()),
        patch("random.choice", return_value="click_link"),
    ):
        ProfileWarmer, _ = get_warmers()
        warmer = ProfileWarmer(tab)
        await warmer.warm_up(
            sites=["https://example.com"],
            sites_count=1,
            duration_per_site=(0.01, 0.02),
            click_random_links=True,
        )

        tab.get.assert_any_call("https://example.com")


def test_profile_warmer_selenium() -> None:
    """Тестирует SyncProfileWarmer с Selenium WebDriver."""
    driver = MagicMock()
    driver.get = MagicMock()
    driver.current_url = "https://example.com"
    driver.execute_script = MagicMock(
        side_effect=lambda js, *args: (
            "https://example.com"
            if "window.location.href" in js
            else ["/about", "/contact"]
        )
    )

    with (
        patch("chutils.scraping.humanize.warmer.move_mouse", MagicMock()),
        patch("chutils.scraping.humanize.warmer.scroll_to", MagicMock()),
        patch("chutils.scraping.humanize.warmer.human_sleep", MagicMock()),
        patch("random.choice", return_value="click_link"),
    ):
        _, SyncProfileWarmer = get_warmers()
        warmer = SyncProfileWarmer(driver)
        warmer.warm_up(
            sites=["https://example.com"],
            sites_count=1,
            duration_per_site=(0.01, 0.02),
            click_random_links=True,
        )

        driver.get.assert_any_call("https://example.com")


def test_default_search_queries_and_helper() -> None:
    """Тестирует банк поисковых запросов и конфигурацию поисковых систем."""
    from chutils.scraping.humanize.warmer import (
        DEFAULT_SEARCH_QUERIES,
        get_random_search_queries,
        get_search_engine_config,
    )

    # 1. Проверяем наличие ключевых категорий
    assert "tech" in DEFAULT_SEARCH_QUERIES
    assert "news" in DEFAULT_SEARCH_QUERIES
    assert "science" in DEFAULT_SEARCH_QUERIES
    assert "lifestyle" in DEFAULT_SEARCH_QUERIES

    # 2. Выборка по категории
    tech_queries = get_random_search_queries(count=2, category="tech")
    assert len(tech_queries) == 2
    for q in tech_queries:
        assert q in DEFAULT_SEARCH_QUERIES["tech"]

    # 3. Общая выборка
    mixed = get_random_search_queries(count=4)
    assert len(mixed) == 4

    # 4. Конфигурация Google и Yandex
    google_cfg = get_search_engine_config("google")
    assert "google.com" in google_cfg["base_url"]
    assert "input_selector" in google_cfg
    assert "organic_selector" in google_cfg

    yandex_cfg = get_search_engine_config("yandex")
    assert "ya.ru" in yandex_cfg["base_url"] or "yandex" in yandex_cfg["base_url"]
    assert "input_selector" in yandex_cfg
    assert "organic_selector" in yandex_cfg

    # 5. Ошибка при неизвестном поисковике
    with pytest.raises(ValueError, match="Неизвестный поисковый движок"):
        get_search_engine_config("unknown_engine")

    # 6. Проверка фильтрации органических ссылок
    from chutils.scraping.humanize.warmer import is_organic_url

    # Валидные органические ссылки
    assert is_organic_url("https://en.wikipedia.org/wiki/Python", "google")
    assert is_organic_url("https://habr.com/ru/articles/12345/", "yandex")

    # Реклама и трекинг
    assert not is_organic_url(
        "https://googleads.g.doubleclick.net/pagead/ads?client=ca", "google"
    )
    assert not is_organic_url(
        "https://www.googleadservices.com/pagead/aclk?sa=L", "google"
    )
    assert not is_organic_url("https://yabs.yandex.ru/count/12345", "yandex")

    # Внутренние ссылки поисковика
    assert not is_organic_url("https://www.google.com/search?q=test", "google")
    assert not is_organic_url("https://ya.ru/search/?text=test", "yandex")
    assert not is_organic_url("https://passport.yandex.ru/auth", "yandex")
    assert not is_organic_url("javascript:void(0)", "google")
    assert not is_organic_url("", "google")


@pytest.mark.asyncio
async def test_profile_warmer_playwright_warm_up_search() -> None:
    """Тестирует метод warm_up_search для Playwright."""
    page = MagicMock()
    page.goto = AsyncMock()
    page.url = "https://www.google.com"
    page.focus = AsyncMock()
    page.keyboard = MagicMock()
    page.keyboard.type = AsyncMock()
    page.keyboard.press = AsyncMock()
    page.evaluate = AsyncMock(
        return_value=[
            "https://en.wikipedia.org/wiki/Python",
            "https://googleads.g.doubleclick.net/ad",
        ]
    )

    with (
        patch(
            "chutils.scraping.humanize.warmer.async_type_text", AsyncMock()
        ) as mock_type,
        patch("chutils.scraping.humanize.warmer.async_move_mouse", AsyncMock()),
        patch("chutils.scraping.humanize.warmer.async_scroll_to", AsyncMock()),
        patch("chutils.scraping.humanize.warmer.async_human_sleep", AsyncMock()),
    ):
        ProfileWarmer, _ = get_warmers()
        warmer = ProfileWarmer(page)
        await warmer.warm_up_search(
            queries=["python programming"],
            search_engine="google",
            click_result=True,
            surf_result_duration=(0.01, 0.02),
        )

        page.goto.assert_any_call("https://www.google.com")
        page.goto.assert_any_call("https://en.wikipedia.org/wiki/Python")
        assert mock_type.await_count > 0


@pytest.mark.asyncio
async def test_profile_warmer_nodriver_warm_up_search() -> None:
    """Тестирует метод warm_up_search для nodriver."""
    tab = AsyncMock()
    tab._is_nodriver = True
    tab.get = AsyncMock()
    tab.url = "https://www.google.com"
    tab.evaluate = AsyncMock(
        return_value=[
            "https://habr.com/ru/post/12345/",
            "https://yabs.yandex.ru/ad",
        ]
    )

    with (
        patch(
            "chutils.scraping.humanize.warmer.async_type_text", AsyncMock()
        ) as mock_type,
        patch("chutils.scraping.humanize.warmer.async_move_mouse", AsyncMock()),
        patch("chutils.scraping.humanize.warmer.async_scroll_to", AsyncMock()),
        patch("chutils.scraping.humanize.warmer.async_human_sleep", AsyncMock()),
    ):
        ProfileWarmer, _ = get_warmers()
        warmer = ProfileWarmer(tab)
        await warmer.warm_up_search(
            queries=["python async"],
            search_engine="google",
            click_result=True,
            surf_result_duration=(0.01, 0.02),
        )

        tab.get.assert_any_call("https://www.google.com")
        tab.get.assert_any_call("https://habr.com/ru/post/12345/")
        assert mock_type.await_count > 0


def test_profile_warmer_selenium_warm_up_search() -> None:
    """Тестирует метод warm_up_search для Selenium."""
    driver = MagicMock()
    driver.get = MagicMock()
    driver.current_url = "https://www.google.com"
    driver.execute_script = MagicMock(
        return_value=[
            "https://docs.python.org/3/",
            "https://googleads.g.doubleclick.net/ad",
        ]
    )

    with (
        patch("chutils.scraping.humanize.warmer.type_text", MagicMock()) as mock_type,
        patch("chutils.scraping.humanize.warmer.move_mouse", MagicMock()),
        patch("chutils.scraping.humanize.warmer.scroll_to", MagicMock()),
        patch("chutils.scraping.humanize.warmer.human_sleep", MagicMock()),
    ):
        _, SyncProfileWarmer = get_warmers()
        warmer = SyncProfileWarmer(driver)
        warmer.warm_up_search(
            queries=["python official docs"],
            search_engine="google",
            click_result=True,
            surf_result_duration=(0.01, 0.02),
        )

        driver.get.assert_any_call("https://www.google.com")
        driver.get.assert_any_call("https://docs.python.org/3/")
        assert mock_type.call_count > 0


@pytest.mark.asyncio
async def test_warm_up_search_captcha_handling() -> None:
    """Тестирует корректную и безопасную реакцию на появление капчи/блокировки."""
    page = MagicMock()
    page.goto = AsyncMock()
    page.url = "https://www.google.com/sorry/index?continue=..."
    page.evaluate = AsyncMock(return_value="recaptcha")

    with (
        patch("chutils.scraping.humanize.warmer.async_type_text", AsyncMock()),
        patch("chutils.scraping.humanize.warmer.async_human_sleep", AsyncMock()),
    ):
        ProfileWarmer, _ = get_warmers()
        warmer = ProfileWarmer(page)
        # Не должно выбрасывать исключений
        await warmer.warm_up_search(queries=["test query"])


@pytest.mark.asyncio
async def test_warmer_save_profile(tmp_path) -> None:
    """Тестирует сохранение профиля через ProfileWarmer.save_profile."""
    page = MagicMock()
    context = AsyncMock()
    page.context = context
    context.storage_state.return_value = {
        "cookies": [{"name": "c", "value": "1", "domain": "test.com", "path": "/"}],
        "origins": [],
    }

    ProfileWarmer, _ = get_warmers()
    warmer = ProfileWarmer(page)
    file_path = tmp_path / "warmer_export.chprofile"
    profile = await warmer.save_profile(file_path, metadata={"run": "1"})

    assert profile.metadata["warmed_up"] == "true"
    assert profile.metadata["run"] == "1"
    assert file_path.exists()


def test_sync_warmer_save_profile(tmp_path) -> None:
    """Тестирует сохранение профиля через SyncProfileWarmer.save_profile."""
    driver = MagicMock()
    driver.get_cookies.return_value = [
        {"name": "c", "value": "2", "domain": "test.com", "path": "/"}
    ]
    driver.execute_script.return_value = "Chrome UA"

    _, SyncProfileWarmer = get_warmers()
    warmer = SyncProfileWarmer(driver)
    file_path = tmp_path / "sync_warmer_export.chprofile"
    profile = warmer.save_profile(file_path, metadata={"run": "sync"})

    assert profile.metadata["warmed_up"] == "true"
    assert profile.metadata["run"] == "sync"
    assert file_path.exists()
