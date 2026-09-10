"""Тесты для пула прокси ProxyPool и проверки здоровья (chutils.scraping.proxy)."""

import time
from unittest.mock import MagicMock, patch

import pytest

from chutils.scraping.proxy.models import ProxyConfig, ProxyHealthResult
from chutils.scraping.proxy.pool import ProxyPool, check_proxy, check_proxy_async


def test_proxy_pool_round_robin() -> None:
    """Проверяет стратегию round_robin."""
    proxies = [
        "1.1.1.1:8080",
        "2.2.2.2:8080",
        "3.3.3.3:8080",
    ]
    pool = ProxyPool(proxies=proxies, strategy="round_robin")
    assert len(pool.get_all()) == 3

    p1 = pool.get_next()
    p2 = pool.get_next()
    p3 = pool.get_next()
    p4 = pool.get_next()

    assert p1 is not None and p1.host == "1.1.1.1"
    assert p2 is not None and p2.host == "2.2.2.2"
    assert p3 is not None and p3.host == "3.3.3.3"
    assert p4 is not None and p4.host == "1.1.1.1"


def test_proxy_pool_random() -> None:
    """Проверяет стратегию random."""
    proxies = ["1.1.1.1:8080", "2.2.2.2:8080"]
    pool = ProxyPool(proxies=proxies, strategy="random")
    for _ in range(10):
        p = pool.get_next()
        assert p is not None
        assert p.host in ("1.1.1.1", "2.2.2.2")


def test_proxy_pool_sticky() -> None:
    """Проверяет стратегию sticky с фиксацией по ключу сессии и TTL."""
    proxies = ["1.1.1.1:8080", "2.2.2.2:8080", "3.3.3.3:8080"]
    pool = ProxyPool(proxies=proxies, strategy="sticky", sticky_ttl=10.0)

    # При одинаковом ключе возвращается один и тот же прокси
    p_user1_a = pool.get_next(key="user_1")
    p_user1_b = pool.get_next(key="user_1")
    assert p_user1_a is not None and p_user1_b is not None
    assert p_user1_a.host == p_user1_b.host

    # Для другого ключа привязывается прокси
    p_user2 = pool.get_next(key="user_2")
    assert p_user2 is not None

    # Проверяем истечение TTL
    with patch("time.time", return_value=time.time() + 100):
        # Должен произойти выбор нового прокси
        p_user1_c = pool.get_next(key="user_1")
        assert p_user1_c is not None


def test_proxy_pool_failover_and_ban() -> None:
    """Проверяет стратегию failover и исключение сбойных прокси."""
    proxies = ["1.1.1.1:8080", "2.2.2.2:8080"]
    pool = ProxyPool(
        proxies=proxies,
        strategy="round_robin",
        ban_timeout=60.0,
        max_fails=2,
    )

    # 1.1.1.1 падает дважды
    p1 = pool.get_next()
    assert p1 is not None and p1.host == "1.1.1.1"
    pool.report_failure(p1)
    # Еще доступен, так как max_fails = 2
    assert len(pool.get_available()) == 2

    pool.report_failure(p1)
    # Теперь 1.1.1.1 временно забанен
    available = pool.get_available()
    assert len(available) == 1
    assert available[0].host == "2.2.2.2"

    # Теперь все вызовы возвращают 2.2.2.2
    assert pool.get_next().host == "2.2.2.2"  # type: ignore[union-attr]

    # Успешный репорт сбрасывает ошибки
    pool.report_success("2.2.2.2:8080")

    # Спустя ban_timeout 1.1.1.1 возвращается в строй
    with patch("time.time", return_value=time.time() + 70):
        assert len(pool.get_available()) == 2


def test_proxy_pool_add_remove() -> None:
    """Проверяет добавление и удаление прокси из пула."""
    pool = ProxyPool()
    assert len(pool.get_all()) == 0
    assert pool.get_next() is None

    pool.add("1.1.1.1:8080")
    pool.add(ProxyConfig(host="2.2.2.2", port=8080, protocol="http"))
    assert len(pool.get_all()) == 2

    removed = pool.remove("1.1.1.1:8080")
    assert removed
    assert len(pool.get_all()) == 1
    assert pool.get_next().host == "2.2.2.2"  # type: ignore[union-attr]


def test_check_proxy_success() -> None:
    """Проверяет успешный health check прокси."""
    proxy = ProxyConfig(host="proxy.test", port=8080, protocol="http")

    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read.return_value = b'{"ip": "198.51.100.1"}'

    with patch("urllib.request.build_opener") as mock_opener:
        mock_instance = MagicMock()
        mock_instance.open.return_value.__enter__.return_value = mock_resp
        mock_opener.return_value = mock_instance

        res = check_proxy(proxy, timeout=3.0)
        assert res.is_alive
        assert res.external_ip == "198.51.100.1"
        assert res.latency_ms >= 0
        assert res.error is None


def test_check_proxy_failure() -> None:
    """Проверяет обработку сетевой ошибки при проверке прокси."""
    proxy = ProxyConfig(host="dead.proxy", port=8080, protocol="http")

    with patch("urllib.request.build_opener") as mock_opener:
        mock_instance = MagicMock()
        mock_instance.open.side_effect = TimeoutError("Connection timed out")
        mock_opener.return_value = mock_instance

        res = check_proxy(proxy, timeout=1.0)
        assert not res.is_alive
        assert res.external_ip is None
        assert "timed out" in (res.error or "")


@pytest.mark.asyncio
async def test_check_proxy_async() -> None:
    """Проверяет асинхронную проверку прокси."""
    proxy = ProxyConfig(host="async.proxy", port=8080, protocol="http")
    mock_res = ProxyHealthResult(
        is_alive=True, latency_ms=12.5, external_ip="203.0.113.5"
    )

    with patch(
        "chutils.scraping.proxy.pool.check_proxy", return_value=mock_res
    ) as mock_sync:
        res = await check_proxy_async(proxy)
        assert res.is_alive
        assert res.external_ip == "203.0.113.5"
        mock_sync.assert_called_once()
