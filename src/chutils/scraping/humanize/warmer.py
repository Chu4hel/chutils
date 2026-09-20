import asyncio
import random
import time
import urllib.parse
from pathlib import Path
from typing import Any

from chutils.logger import setup_logger

from .actions import (
    _ensure_nodriver,
    _is_nodriver,
    _is_playwright,
    async_human_sleep,
    async_move_mouse,
    async_scroll_to,
    async_type_text,
    human_sleep,
    move_mouse,
    scroll_to,
    type_text,
)
from .search import (
    DEFAULT_SEARCH_QUERIES,
    _is_bot_detection,
    get_random_search_queries,
    get_search_engine_config,
    is_organic_url,
)

logger = setup_logger(__name__)

DEFAULT_TRUST_SITES = [
    "https://www.google.com",
    "https://www.wikipedia.org",
    "https://www.reddit.com",
    "https://www.youtube.com",
    "https://github.com",
    "https://www.yandex.ru",
]


class ProfileWarmer:
    """
    Класс для асинхронного прогрева браузерных профилей (Playwright, nodriver).

    Обеспечивает естественный цифровой след путем посещения сайтов, скроллинга,
    имитации мыши и переходов по внутренним ссылкам.
    """

    def __init__(self, browser_or_tab: Any) -> None:
        """Инициализирует ProfileWarmer.

        Args:
            browser_or_tab: Объект страницы Playwright Page или вкладки nodriver Tab.
        """
        self.browser_or_tab = browser_or_tab

    async def warm_up(
        self,
        sites: list[str] | None = None,
        sites_count: int = 3,
        duration_per_site: tuple[float, float] = (10.0, 30.0),
        click_random_links: bool = True,
    ) -> None:
        """Запускает процесс прогрева профиля.

        Args:
            sites: Список URL-адресов трастовых сайтов для прогрева. Если None, используется встроенный список.
            sites_count: Количество посещаемых сайтов.
            duration_per_site: Диапазон времени пребывания на одном сайте (мин, макс в секундах).
            click_random_links: Флаг перехода по случайным внутренним ссылкам.
        """
        target_sites = sites or DEFAULT_TRUST_SITES
        chosen_sites = random.sample(target_sites, min(sites_count, len(target_sites)))

        for url in chosen_sites:
            try:
                # 1. Навигация
                if _is_nodriver(self.browser_or_tab):
                    await self.browser_or_tab.get(url)
                elif _is_playwright(self.browser_or_tab):
                    await self.browser_or_tab.goto(url)
                else:
                    raise ValueError(
                        f"Не удалось определить тип переданного объекта: {type(self.browser_or_tab)}. "
                        "Убедитесь, что передан объект Playwright (Page) или nodriver (Tab/Element)."
                    )

                # Даем странице загрузиться
                await async_human_sleep(2.0, 4.0)

                # Вычисляем время пребывания на сайте
                site_duration = random.uniform(*duration_per_site)
                start_time = asyncio.get_event_loop().time()
                first_run = True

                # Имитация человеческих действий
                while first_run or (
                    asyncio.get_event_loop().time() - start_time < site_duration
                ):
                    first_run = False
                    action = random.choice(
                        [
                            "scroll",
                            "mouse",
                            "sleep",
                            "click_link" if click_random_links else "sleep",
                        ]
                    )

                    if action == "scroll":
                        scroll_x = random.randint(0, 50)
                        scroll_y = random.randint(150, 900)
                        await async_scroll_to(
                            self.browser_or_tab,
                            scroll_x,
                            scroll_y,
                            steps=random.randint(5, 12),
                            delay_between_steps=0.01,
                        )
                    elif action == "mouse":
                        dest_x = random.randint(50, 750)
                        dest_y = random.randint(50, 550)
                        await async_move_mouse(
                            self.browser_or_tab,
                            dest_x,
                            dest_y,
                            steps=random.randint(10, 20),
                            delay_between_steps=0.005,
                        )
                    elif action == "sleep":
                        await async_human_sleep(1.0, 3.0)
                    elif action == "click_link":
                        curr_url = self.browser_or_tab.url
                        links = await self.browser_or_tab.evaluate("""() => {
                            return Array.from(document.querySelectorAll('a[href]'))
                                .map(a => a.getAttribute('href'))
                                .filter(href => href && (href.startsWith('/') || href.startsWith(window.location.origin)));
                        }""")

                        if links:
                            link = random.choice(links)
                            target_url = urllib.parse.urljoin(curr_url, link)
                            try:
                                if _is_nodriver(self.browser_or_tab):
                                    await self.browser_or_tab.get(target_url)
                                else:
                                    await self.browser_or_tab.goto(target_url)
                                await async_human_sleep(2.0, 4.0)
                            except Exception:
                                pass
            except Exception:
                pass

    async def warm_up_search(
        self,
        queries: list[str] | None = None,
        category: str | None = None,
        queries_count: int = 2,
        search_engine: str = "google",
        click_result: bool = True,
        surf_result_duration: tuple[float, float] = (5.0, 15.0),
    ) -> None:
        """Симулирует органический поиск и серфинг по результатам выдачи.

        Args:
            queries: Список поисковых запросов. Если None, выбираются случайные запросы из банка.
            category: Категория запросов ('tech', 'news', 'science', 'lifestyle'), если queries is None.
            queries_count: Количество запросов для поиска.
            search_engine: Поисковая система ('google' или 'yandex').
            click_result: Переходить ли по органической ссылке из выдачи.
            surf_result_duration: Время пребывания на целевом сайте после перехода (мин, макс в секундах).
        """
        if queries is not None:
            chosen_queries = queries[:queries_count]
        else:
            chosen_queries = get_random_search_queries(
                count=queries_count, category=category
            )

        config = get_search_engine_config(search_engine)

        for query in chosen_queries:
            try:
                base_url = config["base_url"]
                if _is_nodriver(self.browser_or_tab):
                    await self.browser_or_tab.get(base_url)
                elif _is_playwright(self.browser_or_tab):
                    await self.browser_or_tab.goto(base_url)
                else:
                    raise ValueError(
                        f"Не удалось определить тип переданного объекта: {type(self.browser_or_tab)}."
                    )

                await async_human_sleep(1.5, 3.0)

                curr_url = getattr(self.browser_or_tab, "url", "")
                if _is_bot_detection(curr_url):
                    logger.warning(
                        "Обнаружена страница проверки бота/капчи (%s). Прогрев поиска прерван.",
                        curr_url,
                    )
                    return

                input_selector = config["input_selector"]
                typed = False
                try:
                    await async_type_text(
                        self.browser_or_tab,
                        input_selector,
                        query,
                        error_rate=0.03,
                        speed_wpm=45.0,
                    )
                    typed = True
                except Exception as ex:
                    logger.debug("Не удалось ввести запрос в поисковую строку: %s", ex)

                if typed:
                    if _is_playwright(self.browser_or_tab):
                        try:
                            await self.browser_or_tab.keyboard.press("Enter")
                        except Exception:
                            pass
                    elif _is_nodriver(self.browser_or_tab):
                        try:
                            _ensure_nodriver()
                            from nodriver.cdp import input_ as cdp_input

                            await self.browser_or_tab.send(
                                cdp_input.dispatch_key_event(
                                    type_="keyDown",
                                    key="Enter",
                                    code="Enter",
                                    windows_virtual_key_code=13,
                                )
                            )
                            await self.browser_or_tab.send(
                                cdp_input.dispatch_key_event(
                                    type_="keyUp",
                                    key="Enter",
                                    code="Enter",
                                    windows_virtual_key_code=13,
                                )
                            )
                        except Exception:
                            pass
                else:
                    search_url = config["search_url"].format(
                        query=urllib.parse.quote_plus(query)
                    )
                    if _is_nodriver(self.browser_or_tab):
                        await self.browser_or_tab.get(search_url)
                    else:
                        await self.browser_or_tab.goto(search_url)

                await async_human_sleep(2.0, 4.0)

                curr_url = getattr(self.browser_or_tab, "url", "")
                if _is_bot_detection(curr_url):
                    logger.warning(
                        "Обнаружена страница проверки бота/капчи (%s). Прогрев поиска прерван.",
                        curr_url,
                    )
                    return

                # Просмотр поисковой выдачи: скроллинг и движения мыши
                scroll_y = random.randint(200, 600)
                await async_scroll_to(
                    self.browser_or_tab,
                    0,
                    scroll_y,
                    steps=random.randint(6, 12),
                    delay_between_steps=0.01,
                )
                await async_move_mouse(
                    self.browser_or_tab,
                    random.randint(100, 700),
                    random.randint(150, 500),
                    steps=random.randint(10, 20),
                )
                await async_human_sleep(1.5, 3.5)

                if click_result:
                    links = await self.browser_or_tab.evaluate("""() => {
                        return Array.from(document.querySelectorAll('a[href]'))
                            .map(a => a.href)
                            .filter(Boolean);
                    }""")

                    if isinstance(links, list):
                        organic_links = [
                            link
                            for link in links
                            if is_organic_url(link, search_engine)
                        ]

                        if organic_links:
                            chosen_link = random.choice(
                                organic_links[: min(5, len(organic_links))]
                            )
                            if _is_nodriver(self.browser_or_tab):
                                await self.browser_or_tab.get(chosen_link)
                            else:
                                await self.browser_or_tab.goto(chosen_link)

                            await async_human_sleep(2.0, 4.0)

                            surf_duration = random.uniform(*surf_result_duration)
                            start_time = asyncio.get_event_loop().time()
                            while (
                                asyncio.get_event_loop().time() - start_time
                                < surf_duration
                            ):
                                await async_scroll_to(
                                    self.browser_or_tab,
                                    0,
                                    random.randint(100, 700),
                                    steps=random.randint(5, 10),
                                )
                                await async_move_mouse(
                                    self.browser_or_tab,
                                    random.randint(100, 600),
                                    random.randint(100, 500),
                                )
                                await async_human_sleep(1.5, 3.0)
            except Exception as ex:
                logger.debug("Ошибка в ходе асинхронного прогрева поиска: %s", ex)

    async def save_profile(
        self,
        filepath: str | Path,
        password: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> Any:
        """Экспортирует сессию после прогрева и сохраняет её в .chprofile файл через ProfileManager.

        Args:
            filepath: Путь к сохраняемому файлу (.chprofile).
            password: Опциональный пароль для шифрования данных профиля.
            metadata: Пользовательские метаданные.

        Returns:
            Экземпляр BrowserProfile.
        """
        from chutils.scraping.profiles.manager import ProfileManager

        driver_type = "nodriver" if _is_nodriver(self.browser_or_tab) else "playwright"
        return await ProfileManager.save_profile_after_warmup(
            self.browser_or_tab,
            filepath=filepath,
            password=password,
            metadata=metadata,
            driver_type=driver_type,
        )


class SyncProfileWarmer:
    """
    Класс для синхронного прогрева браузерных профилей (Selenium).
    """

    def __init__(self, driver: Any) -> None:
        """Инициализирует SyncProfileWarmer.

        Args:
            driver: Экземпляр Selenium WebDriver.
        """
        self.driver = driver

    def warm_up(
        self,
        sites: list[str] | None = None,
        sites_count: int = 3,
        duration_per_site: tuple[float, float] = (10.0, 30.0),
        click_random_links: bool = True,
    ) -> None:
        """Запускает процесс прогрева профиля (синхронно).

        Args:
            sites: Список URL-адресов трастовых сайтов для прогрева. Если None, используется встроенный список.
            sites_count: Количество посещаемых сайтов.
            duration_per_site: Диапазон времени пребывания на одном сайте (мин, макс в секундах).
            click_random_links: Флаг перехода по случайным внутренним ссылкам.
        """
        target_sites = sites or DEFAULT_TRUST_SITES
        chosen_sites = random.sample(target_sites, min(sites_count, len(target_sites)))

        for url in chosen_sites:
            try:
                self.driver.get(url)
                human_sleep(2.0, 4.0)

                site_duration = random.uniform(*duration_per_site)
                start_time = time.time()
                first_run = True

                while first_run or (time.time() - start_time < site_duration):
                    first_run = False
                    action = random.choice(
                        [
                            "scroll",
                            "mouse",
                            "sleep",
                            "click_link" if click_random_links else "sleep",
                        ]
                    )

                    if action == "scroll":
                        scroll_x = random.randint(0, 50)
                        scroll_y = random.randint(150, 900)
                        scroll_to(
                            self.driver,
                            scroll_x,
                            scroll_y,
                            steps=random.randint(5, 12),
                            delay_between_steps=0.01,
                        )
                    elif action == "mouse":
                        dest_x = random.randint(50, 750)
                        dest_y = random.randint(50, 550)
                        move_mouse(
                            self.driver,
                            dest_x,
                            dest_y,
                            steps=random.randint(10, 20),
                            delay_between_steps=0.005,
                        )
                    elif action == "sleep":
                        human_sleep(1.0, 3.0)
                    elif action == "click_link":
                        curr_url = self.driver.current_url
                        links = self.driver.execute_script("""
                            return Array.from(document.querySelectorAll('a[href]'))
                                .map(a => a.getAttribute('href'))
                                .filter(href => href && (href.startsWith('/') || href.startsWith(window.location.origin)));
                        """)

                        if links:
                            link = random.choice(links)
                            target_url = urllib.parse.urljoin(curr_url, link)
                            try:
                                self.driver.get(target_url)
                                human_sleep(2.0, 4.0)
                            except Exception:
                                pass
            except Exception:
                pass

    def warm_up_search(
        self,
        queries: list[str] | None = None,
        category: str | None = None,
        queries_count: int = 2,
        search_engine: str = "google",
        click_result: bool = True,
        surf_result_duration: tuple[float, float] = (5.0, 15.0),
    ) -> None:
        """Синхронно симулирует органический поиск и серфинг по результатам выдачи Selenium.

        Args:
            queries: Список поисковых запросов. Если None, выбираются случайные запросы из банка.
            category: Категория запросов ('tech', 'news', 'science', 'lifestyle'), если queries is None.
            queries_count: Количество запросов для поиска.
            search_engine: Поисковая система ('google' или 'yandex').
            click_result: Переходить ли по органической ссылке из выдачи.
            surf_result_duration: Время пребывания на целевом сайте после перехода (мин, макс в секундах).
        """
        if queries is not None:
            chosen_queries = queries[:queries_count]
        else:
            chosen_queries = get_random_search_queries(
                count=queries_count, category=category
            )

        config = get_search_engine_config(search_engine)

        for query in chosen_queries:
            try:
                base_url = config["base_url"]
                self.driver.get(base_url)
                human_sleep(1.5, 3.0)

                curr_url = getattr(self.driver, "current_url", "")
                if _is_bot_detection(curr_url):
                    logger.warning(
                        "Обнаружена страница проверки бота/капчи (%s). Прогрев поиска прерван.",
                        curr_url,
                    )
                    return

                input_selector = config["input_selector"]
                typed = False
                try:
                    type_text(
                        self.driver,
                        input_selector,
                        query,
                        error_rate=0.03,
                        speed_wpm=45.0,
                    )
                    typed = True
                except Exception as ex:
                    logger.debug("Не удалось ввести запрос в Selenium: %s", ex)

                if typed:
                    try:
                        from selenium.webdriver.common.by import By
                        from selenium.webdriver.common.keys import Keys

                        input_elem = self.driver.find_element(
                            By.CSS_SELECTOR, input_selector
                        )
                        input_elem.send_keys(Keys.ENTER)
                    except Exception:
                        pass
                else:
                    search_url = config["search_url"].format(
                        query=urllib.parse.quote_plus(query)
                    )
                    self.driver.get(search_url)

                human_sleep(2.0, 4.0)

                curr_url = getattr(self.driver, "current_url", "")
                if _is_bot_detection(curr_url):
                    logger.warning(
                        "Обнаружена страница проверки бота/капчи (%s). Прогрев поиска прерван.",
                        curr_url,
                    )
                    return

                # Просмотр выдачи
                scroll_y = random.randint(200, 600)
                scroll_to(self.driver, 0, scroll_y, steps=random.randint(6, 12))
                move_mouse(
                    self.driver,
                    random.randint(100, 700),
                    random.randint(150, 500),
                    steps=random.randint(10, 20),
                )
                human_sleep(1.5, 3.5)

                if click_result:
                    links = self.driver.execute_script("""
                        return Array.from(document.querySelectorAll('a[href]'))
                            .map(a => a.href)
                            .filter(Boolean);
                    """)

                    if isinstance(links, list):
                        organic_links = [
                            link
                            for link in links
                            if is_organic_url(link, search_engine)
                        ]

                        if organic_links:
                            chosen_link = random.choice(
                                organic_links[: min(5, len(organic_links))]
                            )
                            self.driver.get(chosen_link)
                            human_sleep(2.0, 4.0)

                            surf_duration = random.uniform(*surf_result_duration)
                            start_time = time.time()
                            while time.time() - start_time < surf_duration:
                                scroll_to(
                                    self.driver,
                                    0,
                                    random.randint(100, 700),
                                    steps=random.randint(5, 10),
                                )
                                move_mouse(
                                    self.driver,
                                    random.randint(100, 600),
                                    random.randint(100, 500),
                                )
                                human_sleep(1.5, 3.0)
            except Exception as ex:
                logger.debug("Ошибка в ходе синхронного прогрева поиска: %s", ex)

    def save_profile(
        self,
        filepath: str | Path,
        password: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> Any:
        """Синхронно экспортирует сессию Selenium и сохраняет в .chprofile файл через ProfileManager.

        Args:
            filepath: Путь к сохраняемому файлу (.chprofile).
            password: Опциональный пароль для шифрования.
            metadata: Пользовательские метаданные.

        Returns:
            Экземпляр BrowserProfile.
        """
        import datetime

        from chutils.scraping.profiles.manager import ProfileManager

        profile = ProfileManager.export_from_selenium(self.driver)
        profile.metadata["warmed_up"] = "true"
        profile.metadata["last_warmed_up_at"] = datetime.datetime.now(
            datetime.timezone.utc
        ).isoformat()
        if metadata:
            profile.metadata.update(metadata)
        ProfileManager.save(profile, filepath=filepath, password=password)
        return profile


__all__ = [
    "DEFAULT_SEARCH_QUERIES",
    "ProfileWarmer",
    "SyncProfileWarmer",
    "get_random_search_queries",
    "get_search_engine_config",
    "is_organic_url",
]
