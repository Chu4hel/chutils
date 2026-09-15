"""Пул прокси-серверов со стратегиями ротации, failover и проверкой доступности."""

import asyncio
import json
import random
import re
import threading
import time
import urllib.request
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from chutils.logger import setup_logger
from chutils.scraping.proxy.models import ProxyConfig, ProxyHealthResult
from chutils.scraping.proxy.parser import parse_proxy

logger = setup_logger(__name__)

RotationStrategy = Literal["round_robin", "random", "sticky", "failover"]


@dataclass
class _ProxyEntry:
    """Внутреннее состояние прокси в пуле."""

    proxy: ProxyConfig
    failed_attempts: int = 0
    disabled_until: float = 0.0
    success_count: int = 0

    @property
    def is_available(self) -> bool:
        """Проверяет доступность прокси с учетом таймаута бана."""
        if self.disabled_until <= 0:
            return True
        return time.time() >= self.disabled_until


class ProxyPool:
    """Потокобезопасный пул прокси-серверов с поддержкой ротации и автоматического failover."""

    def __init__(
        self,
        proxies: Sequence[ProxyConfig | str | dict[str, object]] | None = None,
        strategy: RotationStrategy = "round_robin",
        sticky_ttl: float = 600.0,
        ban_timeout: float = 300.0,
        max_fails: int = 3,
    ) -> None:
        """Инициализирует пул прокси.

        Args:
            proxies: Начальный список прокси (объекты, строки или словари).
            strategy: Стратегия ротации ('round_robin', 'random', 'sticky', 'failover').
            sticky_ttl: Время жизни привязки сессии/пользователя в секундах для sticky.
            ban_timeout: Время временного исключения сбойного прокси из пула (в секундах).
            max_fails: Максимальное количество ошибок до временного отключения прокси.
        """
        self.strategy: RotationStrategy = strategy
        self.sticky_ttl: float = sticky_ttl
        self.ban_timeout: float = ban_timeout
        self.max_fails: int = max_fails

        self._entries: list[_ProxyEntry] = []
        self._lock: threading.RLock = threading.RLock()
        self._rr_index: int = 0
        # key -> (proxy_key, timestamp)
        self._sticky_map: dict[str, tuple[str, float]] = {}

        if proxies:
            for p in proxies:
                self.add(p)

    def add(self, proxy: ProxyConfig | str | dict[str, object]) -> None:
        """Добавляет прокси в пул.

        Args:
            proxy: Конфигурация прокси (ProxyConfig, строка или dict).
        """
        cfg = parse_proxy(proxy)
        with self._lock:
            # Избегаем дубликатов по server_url и username
            key = f"{cfg.url}"
            for entry in self._entries:
                if entry.proxy.url == key:
                    return
            self._entries.append(_ProxyEntry(proxy=cfg))

    def remove(self, proxy: ProxyConfig | str) -> bool:
        """Удаляет прокси из пула.

        Args:
            proxy: Удаляемый прокси (ProxyConfig или строка).

        Returns:
            True, если прокси был найден и удален, иначе False.
        """
        cfg = parse_proxy(proxy)
        with self._lock:
            for i, entry in enumerate(self._entries):
                if entry.proxy.url == cfg.url:
                    self._entries.pop(i)
                    return True
            return False

    def get_all(self) -> list[ProxyConfig]:
        """Возвращает список всех зарегистрированных прокси в пуле.

        Returns:
            Список экземпляров ProxyConfig.
        """
        with self._lock:
            return [e.proxy for e in self._entries]

    def get_available(self) -> list[ProxyConfig]:
        """Возвращает список только доступных (не забаненных) прокси.

        Returns:
            Список доступных экземпляров ProxyConfig.
        """
        with self._lock:
            return [e.proxy for e in self._entries if e.is_available]

    def get_next(self, key: str | None = None) -> ProxyConfig | None:
        """Возвращает следующий прокси согласно выбранной стратегии.

        Args:
            key: Идентификатор сессии/пользователя для стратегии 'sticky'.

        Returns:
            Экземпляр ProxyConfig или None, если нет доступных прокси.
        """
        with self._lock:
            available_entries = [e for e in self._entries if e.is_available]
            if not available_entries:
                return None

            match self.strategy:
                case "random":
                    return random.choice(available_entries).proxy

                case "sticky":
                    if key is not None:
                        now = time.time()
                        if key in self._sticky_map:
                            proxy_url, assigned_time = self._sticky_map[key]
                            if now - assigned_time < self.sticky_ttl:
                                for e in available_entries:
                                    if e.proxy.url == proxy_url:
                                        return e.proxy
                        # Назначаем новый sticky прокси
                        chosen = random.choice(available_entries).proxy
                        self._sticky_map[key] = (chosen.url, now)
                        return chosen
                    return random.choice(available_entries).proxy

                case "round_robin" | "failover" | _:
                    if self._rr_index >= len(available_entries):
                        self._rr_index = 0
                    chosen_entry = available_entries[self._rr_index]
                    self._rr_index = (self._rr_index + 1) % len(available_entries)
                    return chosen_entry.proxy

    def report_failure(self, proxy: ProxyConfig | str) -> None:
        """Фиксирует ошибку при обращении через прокси.

        Args:
            proxy: Прокси, на котором произошел сбой.
        """
        cfg = parse_proxy(proxy)
        with self._lock:
            for entry in self._entries:
                if entry.proxy.url == cfg.url:
                    entry.failed_attempts += 1
                    if entry.failed_attempts >= self.max_fails:
                        entry.disabled_until = time.time() + self.ban_timeout
                        logger.warning(
                            "Прокси %s превысил лимит ошибок (%d) и отключен на %s сек",
                            entry.proxy.masked_url,
                            entry.failed_attempts,
                            self.ban_timeout,
                        )
                    break

    def report_success(self, proxy: ProxyConfig | str) -> None:
        """Фиксирует успешный запрос через прокси, сбрасывая счетчик ошибок.

        Args:
            proxy: Успешно отработавший прокси.
        """
        cfg = parse_proxy(proxy)
        with self._lock:
            for entry in self._entries:
                if entry.proxy.url == cfg.url:
                    entry.failed_attempts = 0
                    entry.disabled_until = 0.0
                    entry.success_count += 1
                    break

    def reset_status(self) -> None:
        """Сбрасывает счетчики ошибок и разблокирует все временно отключенные прокси."""
        with self._lock:
            for entry in self._entries:
                entry.failed_attempts = 0
                entry.disabled_until = 0.0


def check_proxy(
    proxy: ProxyConfig | str,
    target_url: str = "https://api.ipify.org?format=json",
    timeout: float = 5.0,
) -> ProxyHealthResult:
    """Синхронно проверяет доступность прокси, замеряет RTT и определяет внешний IP.

    Args:
        proxy: Проверяемый прокси (ProxyConfig или строка).
        target_url: URL проверочного эндпоинта.
        timeout: Таймаут соединения в секундах.

    Returns:
        Экземпляр ProxyHealthResult с результатами проверки.
    """
    cfg = parse_proxy(proxy)
    proxy_url = cfg.url

    handlers: list[urllib.request.BaseHandler] = [
        urllib.request.ProxyHandler({"http": proxy_url, "https": proxy_url})
    ]
    opener = urllib.request.build_opener(*handlers)
    req = urllib.request.Request(
        target_url,
        headers={"User-Agent": "chutils-proxy-checker/1.0"},
    )

    t0 = time.perf_counter()
    try:
        with opener.open(req, timeout=timeout) as resp:
            data = resp.read()
            latency = (time.perf_counter() - t0) * 1000.0

            text = data.decode("utf-8", errors="ignore")
            external_ip: str | None = None
            try:
                parsed = json.loads(text)
                if isinstance(parsed, dict) and "ip" in parsed:
                    external_ip = str(parsed["ip"])
                elif isinstance(parsed, dict) and "origin" in parsed:
                    external_ip = str(parsed["origin"])
            except Exception:
                pass

            if not external_ip:
                ip_match = re.search(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", text)
                if ip_match:
                    external_ip = ip_match.group(0)

            return ProxyHealthResult(
                is_alive=True,
                latency_ms=round(latency, 2),
                external_ip=external_ip,
            )
    except Exception as e:
        latency = (time.perf_counter() - t0) * 1000.0
        return ProxyHealthResult(
            is_alive=False,
            latency_ms=round(latency, 2),
            error=str(e),
        )


async def check_proxy_async(
    proxy: ProxyConfig | str,
    target_url: str = "https://api.ipify.org?format=json",
    timeout: float = 5.0,
) -> ProxyHealthResult:
    """Асинхронно проверяет доступность прокси в отдельном потоке.

    Args:
        proxy: Проверяемый прокси.
        target_url: URL проверочного эндпоинта.
        timeout: Таймаут соединения в секундах.

    Returns:
        Экземпляр ProxyHealthResult с результатами проверки.
    """
    return await asyncio.to_thread(check_proxy, proxy, target_url, timeout)
