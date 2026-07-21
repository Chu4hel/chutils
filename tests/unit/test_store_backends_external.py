"""
Юнит-тесты для внешних бэкендов RedisStore и MemcachedStore.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from chutils.exceptions import OptionalDependencyError
from chutils.store.backends.memcached import MemcachedStore
from chutils.store.backends.redis import RedisStore


def test_redis_store_missing_dependency() -> None:
    """Проверяет выброс OptionalDependencyError при отсутствии модуля redis."""
    with patch("chutils.store.backends.redis.is_redis_available", return_value=False):
        store = RedisStore()
        with pytest.raises(OptionalDependencyError):
            store.get("key")


def test_redis_store_sync_operations() -> None:
    """Проверяет синхронные операции RedisStore с моком redis.Redis."""
    mock_redis_client = MagicMock()
    mock_redis_client.get.return_value = b"stored_value"
    mock_redis_client.set.return_value = True
    mock_redis_client.delete.return_value = 1
    mock_redis_client.exists.return_value = 1
    mock_redis_client.flushdb.return_value = True

    mock_redis_module = MagicMock()
    mock_redis_module.Redis.from_url.return_value = mock_redis_client

    with patch.dict("sys.modules", {"redis": mock_redis_module}), patch(
        "chutils.store.backends.redis.is_redis_available", return_value=True
    ):
        store = RedisStore(url="redis://localhost:6379/0")

        assert store.get("k1") == b"stored_value"
        mock_redis_client.get.assert_called_with("k1")

        assert store.set("k1", "val", ttl=60)
        mock_redis_client.set.assert_called_with("k1", "val", ex=60)

        assert store.delete("k1")
        mock_redis_client.delete.assert_called_with("k1")

        assert store.exists("k1")
        mock_redis_client.exists.assert_called_with("k1")

        assert store.clear()
        mock_redis_client.flushdb.assert_called_once()


@pytest.mark.asyncio
async def test_redis_store_async_operations() -> None:
    """Проверяет асинхронные операции RedisStore с моком redis.asyncio.Redis."""
    mock_async_redis = MagicMock()
    mock_async_redis.get = AsyncMock(return_value=b"async_value")
    mock_async_redis.set = AsyncMock(return_value=True)
    mock_async_redis.delete = AsyncMock(return_value=1)
    mock_async_redis.exists = AsyncMock(return_value=1)
    mock_async_redis.flushdb = AsyncMock(return_value=True)

    mock_redis = MagicMock()
    mock_redis.asyncio.Redis.from_url.return_value = mock_async_redis

    with patch.dict("sys.modules", {"redis": mock_redis, "redis.asyncio": mock_redis.asyncio}), patch(
        "chutils.store.backends.redis.is_redis_available", return_value=True
    ):
        store = RedisStore(url="redis://localhost:6379/0")

        assert await store.aget("ak1") == b"async_value"
        assert await store.aset("ak1", "val", ttl=10)
        assert await store.adelete("ak1")
        assert await store.aexists("ak1")
        assert await store.aclear()


def test_memcached_store_missing_dependency() -> None:
    """Проверяет выброс OptionalDependencyError при отсутствии pymemcache."""
    with patch("chutils.store.backends.memcached.is_pymemcache_available", return_value=False):
        store = MemcachedStore()
        with pytest.raises(OptionalDependencyError):
            store.get("key")


def test_memcached_store_sync_operations() -> None:
    """Проверяет синхронные операции MemcachedStore с моком pymemcache."""
    mock_client = MagicMock()
    mock_client.get.return_value = b"mem_val"
    mock_client.set.return_value = True
    mock_client.delete.return_value = True
    mock_client.flush_all.return_value = True

    mock_pymemcache = MagicMock()
    mock_pymemcache.client.base.Client.return_value = mock_client

    with patch.dict(
        "sys.modules",
        {"pymemcache": mock_pymemcache, "pymemcache.client.base": mock_pymemcache.client.base},
    ), patch("chutils.store.backends.memcached.is_pymemcache_available", return_value=True):
        store = MemcachedStore(host="127.0.0.1", port=11211)

        assert store.get("mk") == b"mem_val"
        assert store.set("mk", "val", ttl=30)
        mock_client.set.assert_called_with("mk", "val", expire=30)

        assert store.delete("mk")
        assert store.exists("mk")
        assert store.clear()
