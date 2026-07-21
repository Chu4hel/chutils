import asyncio
import random
import time
import urllib.parse
from typing import Any

from .actions import (
    async_move_mouse,
    async_scroll_to,
    async_human_sleep,
    move_mouse,
    scroll_to,
    human_sleep,
    _is_nodriver,
    _is_playwright,
)

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
                while first_run or (asyncio.get_event_loop().time() - start_time < site_duration):
                    first_run = False
                    action = random.choice(
                        ["scroll", "mouse", "sleep", "click_link" if click_random_links else "sleep"]
                    )

                    if action == "scroll":
                        scroll_x = random.randint(0, 50)
                        scroll_y = random.randint(150, 900)
                        await async_scroll_to(
                            self.browser_or_tab, scroll_x, scroll_y, steps=random.randint(5, 12), delay_between_steps=0.01
                        )
                    elif action == "mouse":
                        dest_x = random.randint(50, 750)
                        dest_y = random.randint(50, 550)
                        await async_move_mouse(
                            self.browser_or_tab, dest_x, dest_y, steps=random.randint(10, 20), delay_between_steps=0.005
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
                        ["scroll", "mouse", "sleep", "click_link" if click_random_links else "sleep"]
                    )

                    if action == "scroll":
                        scroll_x = random.randint(0, 50)
                        scroll_y = random.randint(150, 900)
                        scroll_to(
                            self.driver, scroll_x, scroll_y, steps=random.randint(5, 12), delay_between_steps=0.01
                        )
                    elif action == "mouse":
                        dest_x = random.randint(50, 750)
                        dest_y = random.randint(50, 550)
                        move_mouse(
                            self.driver, dest_x, dest_y, steps=random.randint(10, 20), delay_between_steps=0.005
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
