"""
Domain-Aware Rate Limiter для ограничения частоты запросов к отдельным доменам.
"""

from __future__ import annotations

import asyncio
import fnmatch
import time
from urllib.parse import urlparse


class DomainRateLimiter:
    """Ограничитель частоты запросов и параллельных соединений с привязкой к доменам."""

    def __init__(
        self,
        default_delay: float = 1.0,
        domain_rules: dict[str, float] | None = None,
        max_domain_concurrency: dict[str, int] | None = None,
    ) -> None:
        """Инициализирует лимитер.

        Args:
            default_delay: Задержка по умолчанию между запросами к одному домену (в секундах).
            domain_rules: Кастомные задержки по маскам хостов (напр., {"*.wikipedia.org": 2.0}).
            max_domain_concurrency: Максимальное количество одновременных подключений к домену.
        """
        self.default_delay = default_delay
        self.domain_rules = domain_rules or {}
        self.max_domain_concurrency = max_domain_concurrency or {}

        self._lock = asyncio.Lock()
        self._domain_locks: dict[str, asyncio.Lock] = {}
        self._last_request_time: dict[str, float] = {}
        self._active_connections: dict[str, int] = {}
        self._semaphores: dict[str, asyncio.Semaphore] = {}

    def get_domain(self, url: str) -> str:
        """Извлекает домен в нижнем регистре из URL.

        Args:
            url: Целевой URL.

        Returns:
            Имя хоста (домена).
        """
        netloc = urlparse(url).netloc.lower()
        if ":" in netloc:
            netloc = netloc.split(":")[0]
        return netloc or "default"

    def get_rule_key_and_delay(self, domain: str) -> tuple[str, float]:
        """Возвращает ключ группы правил и соответствующую задержку.

        Args:
            domain: Имя домена.

        Returns:
            Кортеж (ключ_правила, задержка).
        """
        for pattern, delay in self.domain_rules.items():
            pattern_clean = pattern.lower()
            if fnmatch.fnmatch(domain, pattern_clean) or fnmatch.fnmatch(domain, f"*.{pattern_clean.lstrip('*.')}"):
                return pattern_clean, delay
        return domain, self.default_delay

    async def acquire(self, url: str) -> None:
        """Запрашивает разрешение на отправку запроса к указанному URL.

        При необходимости выполняет задержку.

        Args:
            url: Целевой URL.
        """
        domain = self.get_domain(url)
        rule_key, delay = self.get_rule_key_and_delay(domain)

        async with self._lock:
            if rule_key not in self._domain_locks:
                self._domain_locks[rule_key] = asyncio.Lock()
            domain_lock = self._domain_locks[rule_key]

            if rule_key in self.max_domain_concurrency and rule_key not in self._semaphores:
                self._semaphores[rule_key] = asyncio.Semaphore(self.max_domain_concurrency[rule_key])
            sem = self._semaphores.get(rule_key)

        if sem is not None:
            await sem.acquire()

        async with domain_lock:
            last_time = self._last_request_time.get(rule_key, 0.0)
            now = time.monotonic()
            elapsed = now - last_time

            if elapsed < delay:
                await asyncio.sleep(delay - elapsed)

            self._last_request_time[rule_key] = time.monotonic()
            self._active_connections[rule_key] = self._active_connections.get(rule_key, 0) + 1

    def release(self, url: str) -> None:
        """Освобождает слот подключения после завершения запроса.

        Args:
            url: Целевой URL.
        """
        domain = self.get_domain(url)
        rule_key, _ = self.get_rule_key_and_delay(domain)

        if rule_key in self._active_connections:
            self._active_connections[rule_key] = max(0, self._active_connections[rule_key] - 1)
        if rule_key in self._semaphores:
            self._semaphores[rule_key].release()
