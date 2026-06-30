"""
Внутренний модуль реализации алгоритмов Token Bucket и Leaky Bucket для Rate Limiting.
"""
from __future__ import annotations

import threading
import time
from typing import Dict, Optional


class TokenBucket:
    """Алгоритм маркерной корзины (Token Bucket)."""

    def __init__(self, capacity: int, period: float) -> None:
        self.capacity = float(capacity)
        self.period = float(period)
        self.refill_rate = self.capacity / self.period
        self.tokens = self.capacity
        self.last_refill = time.monotonic()
        self.next_allowed_time = time.monotonic()
        self.lock = threading.Lock()

    def acquire(self, wait: bool = False) -> Optional[float]:
        """
        Пытается получить токен из корзины.

        Returns:
            Optional[float]: None, если лимит превышен (wait=False),
            иначе время ожидания в секундах (0.0 означает мгновенный доступ).
        """
        with self.lock:
            now = time.monotonic()

            if now >= self.next_allowed_time:
                # Пополняем токены
                elapsed = now - self.last_refill
                self.last_refill = now
                self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)

                if self.tokens >= 1.0:
                    self.tokens -= 1.0
                    return 0.0

                if not wait:
                    return None

                # Вычисляем время ожидания
                missing = 1.0 - self.tokens
                wait_time = missing / self.refill_rate
                self.tokens = 0.0
                self.next_allowed_time = now + wait_time
                self.last_refill = self.next_allowed_time
                return wait_time
            else:
                if not wait:
                    return None

                # Встаем в очередь за предыдущим запросом
                wait_time = self.next_allowed_time - now
                self.next_allowed_time += (1.0 / self.refill_rate)
                self.last_refill = self.next_allowed_time
                return wait_time


class LeakyBucket:
    """Алгоритм дырявого ведра (Leaky Bucket)."""

    def __init__(self, capacity: int, period: float) -> None:
        self.capacity = float(capacity)
        self.period = float(period)
        self.leak_rate = self.capacity / self.period
        self.water_level = 0.0
        self.last_leak = time.monotonic()
        self.next_allowed_time = time.monotonic()
        self.lock = threading.Lock()

    def acquire(self, wait: bool = False) -> Optional[float]:
        """
        Пытается добавить единицу воды в ведро.

        Returns:
            Optional[float]: None, если ведро переполнено (wait=False),
            иначе время ожидания в секундах (0.0 означает мгновенный доступ).
        """
        with self.lock:
            now = time.monotonic()

            if now >= self.next_allowed_time:
                # Вытекание воды
                elapsed = now - self.last_leak
                self.last_leak = now
                self.water_level = max(0.0, self.water_level - elapsed * self.leak_rate)

                if self.water_level + 1.0 <= self.capacity:
                    self.water_level += 1.0
                    return 0.0

                if not wait:
                    return None

                # Вычисляем время ожидания до возможности добавить еще единицу воды
                excess = (self.water_level + 1.0) - self.capacity
                wait_time = excess / self.leak_rate
                self.water_level = self.capacity
                self.next_allowed_time = now + wait_time
                self.last_leak = self.next_allowed_time
                return wait_time
            else:
                if not wait:
                    return None

                # Встаем в очередь
                wait_time = self.next_allowed_time - now
                self.next_allowed_time += (1.0 / self.leak_rate)
                self.last_leak = self.next_allowed_time
                return wait_time


# Глобальный реестр ограничителей частоты
_limiters: Dict[str, TokenBucket | LeakyBucket] = {}
_limiters_lock = threading.Lock()


def get_limiter(
        key: str,
        max_calls: int,
        period: float,
        strategy: str = "token_bucket"
) -> TokenBucket | LeakyBucket:
    """
    Возвращает или создает ограничитель частоты по ключу.
    """
    with _limiters_lock:
        if key not in _limiters:
            if strategy == "leaky_bucket":
                _limiters[key] = LeakyBucket(max_calls, period)
            else:
                _limiters[key] = TokenBucket(max_calls, period)
        return _limiters[key]


def clear_limiters() -> None:
    """Очищает реестр ограничителей (для тестов)."""
    with _limiters_lock:
        _limiters.clear()
