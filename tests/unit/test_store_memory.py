"""
Юнит-тесты для BaseStoreBackend и MemoryStore.
"""
from __future__ import annotations

import time

import pytest

from chutils.store.backends.memory import MemoryStore


def test_memory_store_sync_operations() -> None:
    """Проверяет синхронные операции get, set, delete, exists, clear в MemoryStore."""
    store = MemoryStore()

    # Initial state
    assert not store.exists("key1")
    assert store.get("key1") is None
    assert store.get("key1", default="def") == "def"

    # Set and get
    store.set("key1", "value1")
    assert store.exists("key1")
    assert store.get("key1") == "value1"

    # Set overwrite
    store.set("key1", "value2")
    assert store.get("key1") == "value2"

    # Delete
    assert store.delete("key1")
    assert not store.exists("key1")
    assert not store.delete("key1")  # False on second delete

    # Multiple keys & Clear
    store.set("a", 1)
    store.set("b", 2)
    assert store.exists("a")
    assert store.exists("b")
    store.clear()
    assert not store.exists("a")
    assert not store.exists("b")


def test_memory_store_ttl() -> None:
    """Проверяет истечение срока действия ключей по TTL."""
    store = MemoryStore()

    # Set with 0.1s TTL
    store.set("short_lived", "temp", ttl=1)
    assert store.get("short_lived") == "temp"

    # Set expired item via mocked time or short sleeping
    store.set("quick_expire", "val", ttl=0.05)
    time.sleep(0.06)
    assert not store.exists("quick_expire")
    assert store.get("quick_expire") is None


@pytest.mark.asyncio
async def test_memory_store_async_operations() -> None:
    """Проверяет асинхронные операции aget, aset, adelete, aexists, aclear."""
    store = MemoryStore()

    assert not await store.aexists("async_key")
    assert await store.aget("async_key", default=42) == 42

    await store.aset("async_key", "async_val", ttl=10)
    assert await store.aexists("async_key")
    assert await store.aget("async_key") == "async_val"

    assert await store.adelete("async_key")
    assert not await store.aexists("async_key")

    await store.aset("k1", "v1")
    await store.aset("k2", "v2")
    await store.aclear()
    assert not await store.aexists("k1")
    assert not await store.aexists("k2")
