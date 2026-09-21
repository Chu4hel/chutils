import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from chutils.scraping.proxy.models import ProxyConfig
from chutils.scraping.proxy.resolver import (
    FileCacheBackend,
    ProxyCandidate,
    SmartProxyResolver,
)


def test_proxy_candidate_model() -> None:
    c1 = ProxyCandidate(protocol="http", host="1.2.3.4", port=8080, username="user", password="pwd")
    assert c1.url == "http://user:pwd@1.2.3.4:8080"
    cfg1 = c1.to_proxy_config()
    assert isinstance(cfg1, ProxyConfig)
    assert cfg1.protocol == "http"
    assert cfg1.host == "1.2.3.4"
    assert cfg1.port == 8080
    assert cfg1.username == "user"
    assert cfg1.password == "pwd"

    c2 = ProxyCandidate(protocol="socks5", host="1.2.3.4", port=1080)
    assert c2.url == "socks5://1.2.3.4:1080"
    cfg2 = c2.to_proxy_config()
    assert cfg2.protocol == "socks5"
    assert cfg2.username is None


def test_generate_candidates_various_formats() -> None:
    resolver = SmartProxyResolver()

    # 1. Формат host:port:user:pass (по умолчанию http, затем socks5)
    cands1 = resolver.generate_candidates("1.2.3.4:8080:myuser:mypass")
    assert len(cands1) >= 2
    assert cands1[0] == "http://myuser:mypass@1.2.3.4:8080"
    assert cands1[1] == "socks5://myuser:mypass@1.2.3.4:8080"

    # 2. Формат user:pass:host:port
    cands2 = resolver.generate_candidates("myuser:mypass:1.2.3.4:8080")
    assert len(cands2) >= 2
    assert cands2[0] == "http://myuser:mypass@1.2.3.4:8080"
    assert cands2[1] == "socks5://myuser:mypass@1.2.3.4:8080"

    # 3. Формат user:pass@host:port
    cands3 = resolver.generate_candidates("myuser:mypass@1.2.3.4:8080")
    assert cands3[0] == "http://myuser:mypass@1.2.3.4:8080"
    assert cands3[1] == "socks5://myuser:mypass@1.2.3.4:8080"

    # 4. Формат host:port@user:pass
    cands4 = resolver.generate_candidates("1.2.3.4:8080@myuser:mypass")
    assert cands4[0] == "http://myuser:mypass@1.2.3.4:8080"
    assert cands4[1] == "socks5://myuser:mypass@1.2.3.4:8080"

    # 5. Простой host:port
    cands5 = resolver.generate_candidates("1.2.3.4:8080")
    assert cands5[0] == "http://1.2.3.4:8080"
    assert cands5[1] == "socks5://1.2.3.4:8080"

    # 6. Явный socks5:// в префиксе -> socks5 идет первым
    cands6 = resolver.generate_candidates("socks5://1.2.3.4:8080:myuser:mypass")
    assert cands6[0] == "socks5://myuser:mypass@1.2.3.4:8080"
    assert cands6[1] == "http://myuser:mypass@1.2.3.4:8080"

    # 7. host:port:user
    cands7 = resolver.generate_candidates("1.2.3.4:8080:myuser")
    assert cands7[0] == "http://myuser@1.2.3.4:8080"

    # 8. Пустая строка или None
    assert resolver.generate_candidates("") == []
    assert resolver.generate_candidates(None) == []


def test_file_cache_backend_lifecycle(tmp_path: Path) -> None:
    cache_file = tmp_path / "cache.json"
    cache = FileCacheBackend(cache_file)

    # Проверка отсутствия
    assert cache.get("test_key") is None
    assert not cache.exists("test_key")

    # Установка значения
    cache.set("test_key", "val1", tags=["tag1"])
    assert cache.get("test_key") == "val1"
    assert cache.exists("test_key")

    # Персистентность: новый экземпляр читает с диска
    cache2 = FileCacheBackend(cache_file)
    assert cache2.get("test_key") == "val1"

    # Проверка TTL
    cache.set("expiring", "val2", ttl=-1)
    assert cache.get("expiring") is None

    # Инвалидация по тегу
    cache.set("k1", "v1", tags=["network"])
    cache.set("k2", "v2", tags=["other"])
    cache.invalidate_tag("network")
    assert cache.get("k1") is None
    assert cache.get("k2") == "v2"

    # Удаление и очистка
    cache.delete("k2")
    assert cache.get("k2") is None
    cache.clear()
    assert cache.get("test_key") is None


def _make_mock_writer() -> MagicMock:
    w = MagicMock()
    w.drain = AsyncMock()
    w.wait_closed = AsyncMock()
    return w


@pytest.mark.asyncio
async def test_probe_http_success_and_failure() -> None:
    resolver = SmartProxyResolver()

    # Успешный HTTP CONNECT
    mock_reader = AsyncMock()
    mock_reader.readline.return_value = b"HTTP/1.1 200 Connection established\r\n"
    mock_writer = _make_mock_writer()

    with patch("asyncio.open_connection", new=AsyncMock(return_value=(mock_reader, mock_writer))):
        res = await resolver.probe_proxy("http://user:pass@1.2.3.4:8080")
        assert res is True
        assert mock_writer.write.called

    # 407 Ошибка авторизации
    mock_reader.readline.return_value = b"HTTP/1.1 407 Proxy Authentication Required\r\n"
    with patch("asyncio.open_connection", new=AsyncMock(return_value=(mock_reader, mock_writer))):
        res_fail = await resolver.probe_proxy("http://user:pass@1.2.3.4:8080")
        assert res_fail is False


@pytest.mark.asyncio
async def test_probe_http_fallback_get_204() -> None:
    resolver = SmartProxyResolver()
    mock_reader = AsyncMock()
    # Сначала 405 Method Not Allowed на CONNECT, затем 204 No Content на GET
    mock_reader.readline.side_effect = [
        b"HTTP/1.1 405 Method Not Allowed\r\n",
        b"HTTP/1.1 204 No Content\r\n",
    ]
    mock_writer = _make_mock_writer()

    with patch("asyncio.open_connection", new=AsyncMock(return_value=(mock_reader, mock_writer))):
        assert await resolver.probe_proxy("http://1.2.3.4:8080") is True


@pytest.mark.asyncio
async def test_probe_socks5_lifecycle() -> None:
    resolver = SmartProxyResolver()

    # 1. SOCKS5 без авторизации (0x00)
    mock_reader = AsyncMock()
    mock_reader.readexactly.return_value = b"\x05\x00"
    mock_reader.read.return_value = b"\x05\x00\x00\x01\x00\x00\x00\x00\x00\x00"
    mock_writer = _make_mock_writer()

    with patch("asyncio.open_connection", new=AsyncMock(return_value=(mock_reader, mock_writer))):
        assert await resolver.probe_proxy("socks5://1.2.3.4:1080") is True

    # 2. SOCKS5 с авторизацией (0x02) - успех
    mock_reader = AsyncMock()
    mock_reader.readexactly.side_effect = [
        b"\x05\x02",  # Приветствие: требуется auth
        b"\x01\x00",  # RFC 1929: auth success
    ]
    mock_reader.read.return_value = b"\x05\x00\x00\x01\x00\x00\x00\x00\x00\x00"
    with patch("asyncio.open_connection", new=AsyncMock(return_value=(mock_reader, mock_writer))):
        assert await resolver.probe_proxy("socks5://user:pass@1.2.3.4:1080") is True

    # 3. SOCKS5 с ошибкой авторизации
    mock_reader = AsyncMock()
    mock_reader.readexactly.side_effect = [
        b"\x05\x02",
        b"\x01\x01",  # auth failed
    ]
    with patch("asyncio.open_connection", new=AsyncMock(return_value=(mock_reader, mock_writer))):
        assert await resolver.probe_proxy("socks5://user:pass@1.2.3.4:1080") is False

    # 4. Не SOCKS5 (версия != 5)
    mock_reader = AsyncMock()
    mock_reader.readexactly.return_value = b"\x04\x00"
    with patch("asyncio.open_connection", new=AsyncMock(return_value=(mock_reader, mock_writer))):
        assert await resolver.probe_proxy("socks5://1.2.3.4:1080") is False


@pytest.mark.asyncio
async def test_probe_socks4() -> None:
    resolver = SmartProxyResolver()
    mock_reader = AsyncMock()
    mock_reader.read.return_value = b"\x00\x5A\x00\x50\x01\x01\x01\x01"
    mock_writer = _make_mock_writer()
    with patch("asyncio.open_connection", new=AsyncMock(return_value=(mock_reader, mock_writer))):
        assert await resolver.probe_proxy("socks4://user@1.2.3.4:1080") is True


@pytest.mark.asyncio
async def test_smart_proxy_resolver_resolve_and_cache(tmp_path: Path) -> None:
    cache_path = tmp_path / "proxy_cache.json"
    resolver = SmartProxyResolver(cache_path=cache_path)

    # Пустая строка -> None
    assert await resolver.resolve("") is None

    # Имитируем, что HTTP не прошел, а SOCKS5 ответил успешно
    async def fake_probe(cand: str) -> bool:
        return cand.startswith("socks5://")

    with patch.object(resolver, "probe_proxy", side_effect=fake_probe):
        resolved = await resolver.resolve("1.2.3.4:8080:myuser:mypass")
        assert resolved == "socks5://myuser:mypass@1.2.3.4:8080"

        # Проверяем, что сохранилось в кэше
        assert resolver.cache.get("1.2.3.4:8080:myuser:mypass") == resolved

        # Повторный вызов должен возвращать результат мгновенно из кэша
        with patch.object(resolver, "probe_proxy") as mock_probe:
            cached_res = await resolver.resolve("1.2.3.4:8080:myuser:mypass")
            assert cached_res == resolved
            assert not mock_probe.called

        # Принудительный обход кэша (force=True)
        with patch.object(resolver, "probe_proxy", side_effect=fake_probe) as mock_probe_force:
            forced_res = await resolver.resolve("1.2.3.4:8080:myuser:mypass", force=True)
            assert forced_res == resolved
            assert mock_probe_force.called


@pytest.mark.asyncio
async def test_smart_proxy_resolver_check_health() -> None:
    resolver = SmartProxyResolver()

    with patch.object(resolver, "probe_proxy", new=AsyncMock(return_value=True)):
        health = await resolver.check_health("http://1.2.3.4:8080")
        assert health.is_alive is True
        assert health.latency_ms is not None
        assert health.latency_ms >= 0
        assert health.error is None

    with patch.object(resolver, "probe_proxy", new=AsyncMock(return_value=False)):
        health_dead = await resolver.check_health("http://1.2.3.4:8080")
        assert health_dead.is_alive is False
        assert health_dead.error == "Handshake or connection probe failed"


@pytest.mark.asyncio
async def test_smart_proxy_resolver_resolve_config() -> None:
    resolver = SmartProxyResolver()

    with patch.object(resolver, "probe_proxy", new=AsyncMock(return_value=True)):
        cfg = await resolver.resolve_config("1.2.3.4:8080:myuser:mypass")
        assert isinstance(cfg, ProxyConfig)
        assert cfg.host == "1.2.3.4"
        assert cfg.port == 8080
        assert cfg.username == "myuser"
        assert cfg.password == "mypass"
        assert cfg.protocol == "http"


def test_smart_proxy_resolver_sync_wrappers(tmp_path: Path) -> None:
    cache_path = tmp_path / "proxy_cache.json"
    resolver = SmartProxyResolver(cache_path=cache_path)

    # Пустые значения
    assert resolver.resolve_sync(None) is None
    assert resolver.resolve_config_sync(None) is None

    # Имитируем успешный probe
    with patch.object(resolver, "probe_proxy", new=AsyncMock(return_value=True)):
        res = resolver.resolve_sync("1.2.3.4:8080:user:pass")
        assert res == "http://user:pass@1.2.3.4:8080"

        cfg = resolver.resolve_config_sync("1.2.3.4:8080:user:pass")
        assert isinstance(cfg, ProxyConfig)
        assert cfg.protocol == "http"
        assert cfg.host == "1.2.3.4"
