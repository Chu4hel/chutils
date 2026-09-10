"""Банк поисковых запросов и вспомогательные утилиты для органического серфинга."""

import random
import urllib.parse

DEFAULT_SEARCH_QUERIES: dict[str, list[str]] = {
    "tech": [
        "python async await best practices",
        "fastapi vs litestar performance benchmark",
        "how does chrome devtools protocol work",
        "css flexbox and grid guide",
        "postgresql query optimization tips",
        "git interactive rebase tutorial",
    ],
    "news": [
        "latest world news updates today",
        "technology news and ai breakthroughs",
        "global economic trends forecast",
        "space telescope discoveries",
    ],
    "science": [
        "quantum computing principles explained",
        "renewable energy efficiency records",
        "crispr gene editing latest research",
        "ocean exploration new species",
    ],
    "lifestyle": [
        "healthy meal prep ideas for week",
        "indoor plant care guide for beginners",
        "minimalist home desk setup",
        "best productivity techniques 2026",
    ],
}


def get_random_search_queries(
    count: int = 3, category: str | None = None
) -> list[str]:
    """Возвращает список случайных реалистичных поисковых запросов.

    Args:
        count: Количество запрашиваемых поисковых запросов.
        category: Необязательная категория ('tech', 'news', 'science', 'lifestyle').

    Returns:
        Список строк с поисковыми запросами.
    """
    if category is not None:
        if category not in DEFAULT_SEARCH_QUERIES:
            valid_cats = list(DEFAULT_SEARCH_QUERIES.keys())
            raise ValueError(
                f"Неизвестная категория запросов: '{category}'. Доступные категории: {valid_cats}"
            )
        pool = DEFAULT_SEARCH_QUERIES[category]
    else:
        pool = [
            q for queries in DEFAULT_SEARCH_QUERIES.values() for q in queries
        ]

    chosen = random.sample(pool, min(count, len(pool)))
    return chosen


def get_search_engine_config(engine: str = "google") -> dict[str, str]:
    """Возвращает конфигурацию для органического поиска в указанной поисковой системе.

    Args:
        engine: Имя поисковой системы ('google' или 'yandex').

    Returns:
        Словарь с параметрами (base_url, search_url, input_selector, submit_selector, organic_selector).
    """
    engine_lower = engine.strip().lower()
    if engine_lower == "google":
        return {
            "base_url": "https://www.google.com",
            "search_url": "https://www.google.com/search?q={query}",
            "input_selector": "textarea[name='q'], input[name='q']",
            "submit_selector": "input[name='btnK'], button[type='submit']",
            "organic_selector": "div#search a:has(h3), #rso a:has(h3)",
        }
    elif engine_lower == "yandex":
        return {
            "base_url": "https://ya.ru",
            "search_url": "https://ya.ru/search/?text={query}",
            "input_selector": "input[name='text'], textarea[name='text']",
            "submit_selector": "button[type='submit']",
            "organic_selector": "li.serp-item a.link, a.OrganicTitle-Link",
        }
    else:
        raise ValueError(
            f"Неизвестный поисковый движок: '{engine}'. Поддерживаются: 'google', 'yandex'."
        )


def is_organic_url(url: str, engine: str = "google") -> bool:
    """Проверяет, является ли URL органической внешней ссылкой из поисковой выдачи,
    исключая рекламу, внутренние сервисы поисковика и трекинговые редиректы.

    Args:
        url: Проверяемый URL.
        engine: Имя поисковой системы ('google' или 'yandex').

    Returns:
        True, если ссылка является валидной органической внешней ссылкой, иначе False.
    """
    if not url or not isinstance(url, str):
        return False

    url_clean = url.strip()
    if not (url_clean.startswith("http://") or url_clean.startswith("https://")):
        return False

    parsed = urllib.parse.urlparse(url_clean)
    netloc = parsed.netloc.lower()
    url_lower = url_clean.lower()

    # Рекламные и трекинговые домены
    ad_domains = {
        "googleads.g.doubleclick.net",
        "ad.doubleclick.net",
        "pagead2.googlesyndication.com",
        "yabs.yandex.ru",
        "an.yandex.ru",
        "awaps.yandex.ru",
    }
    if any(ad_domain in netloc for ad_domain in ad_domains):
        return False

    # Шаблоны рекламных редиректов
    ad_patterns = ["/aclk?", "/adclick", "googleadservices.com", "yabs.yandex"]
    if any(pattern in url_lower for pattern in ad_patterns):
        return False

    engine_lower = engine.strip().lower()
    if engine_lower == "google":
        google_internal = ["google.com", "google.ru", "gstatic.com"]
        if any(
            netloc == d or netloc.endswith("." + d) for d in google_internal
        ):
            return False
    elif engine_lower == "yandex":
        yandex_internal = ["yandex.ru", "ya.ru", "yandex.com", "yastatic.net"]
        if any(
            netloc == d or netloc.endswith("." + d) for d in yandex_internal
        ):
            return False

    return True


def _is_bot_detection(url: str, content: str = "") -> bool:
    """Проверяет признаки страницы проверки на роботов или капчи.

    Args:
        url: URL страницы.
        content: Опциональное текстовое содержимое страницы.

    Returns:
        True, если обнаружены признаки капчи или проверки на бота.
    """
    if not url:
        return False
    url_lower = url.lower()
    content_lower = content.lower()
    indicators = [
        "google.com/sorry",
        "recaptcha",
        "cf-turnstile",
        "challenges.cloudflare.com",
        "yandex.ru/showcaptcha",
        "smartcaptcha",
        "bot verification",
    ]
    return any(ind in url_lower or ind in content_lower for ind in indicators)


__all__ = [
    "DEFAULT_SEARCH_QUERIES",
    "_is_bot_detection",
    "get_random_search_queries",
    "get_search_engine_config",
    "is_organic_url",
]

