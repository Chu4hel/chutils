"""
Тесты для DomainRateLimiter.
"""

import asyncio
import time

import pytest

from chutils.scraping.concurrency.limiter import DomainRateLimiter


@pytest.mark.asyncio
async def test_domain_rate_limiter_delay() -> None:
    """Проверяет соблюдение интервала задержки между запросами к одному домену."""
    limiter = DomainRateLimiter(default_delay=0.1)

    t0 = time.monotonic()
    await limiter.acquire("https://example.com/page1")
    limiter.release("https://example.com/page1")

    await limiter.acquire("https://example.com/page2")
    limiter.release("https://example.com/page2")
    t1 = time.monotonic()

    assert (t1 - t0) >= 0.09  # Задержка минимум ~0.1 с


@pytest.mark.asyncio
async def test_domain_rate_limiter_wildcard_matching() -> None:
    """Проверяет правило задержки по маске домена."""
    rules = {"*.wikipedia.org": 0.2}
    limiter = DomainRateLimiter(default_delay=0.01, domain_rules=rules)

    t0 = time.monotonic()
    await limiter.acquire("https://ru.wikipedia.org/wiki/Main")
    limiter.release("https://ru.wikipedia.org/wiki/Main")

    await limiter.acquire("https://en.wikipedia.org/wiki/Main")
    limiter.release("https://en.wikipedia.org/wiki/Main")
    t1 = time.monotonic()

    assert (t1 - t0) >= 0.18
