"""
Юнит-тесты для StoreManager.
"""
from __future__ import annotations

import pytest

from chutils.store.backends.memory import MemoryStore
from chutils.store.manager import StoreManager


class CustomDummy:

    def __init__(self, name: str) -> None:
        self.name = name

    def __eq__(self, other: object) -> bool:
        return isinstance(other, CustomDummy) and self.name == other.name


def test_store_manager_json_serialization() -> None:
    """Проверяет работу StoreManager с JSON сериализацией по умолчанию."""
    backend = MemoryStore()
    manager = StoreManager(backend=backend, serializer="json", prefix="test:")

    # Complex JSON-serializable dict
    data = {"a": 1, "b": [1, 2, 3], "c": True}
    assert manager.set("data", data)
    assert manager.get("data") == data

    # Verify key prefixing in raw backend
    assert backend.exists("test:data")
    assert not backend.exists("data")

    # Delete & Exists
    assert manager.exists("data")
    assert manager.delete("data")
    assert not manager.exists("data")


def test_store_manager_pickle_serialization() -> None:
    """Проверяет работу StoreManager с Pickle сериализацией для кастомных объектов."""
    backend = MemoryStore()
    manager = StoreManager(backend=backend, serializer="pickle")

    dummy = CustomDummy("test_object")
    assert manager.set("dummy", dummy)
    retrieved = manager.get("dummy")
    assert retrieved == dummy


def test_store_manager_from_config() -> None:
    """Проверяет создание StoreManager из словаря конфигурации."""
    config = {
        "backend": "memory",
        "serializer": "json",
        "prefix": "cfg:",
    }
    manager = StoreManager.from_config(config)
    assert manager.set("num", 100)
    assert manager.get("num") == 100
    assert manager.exists("num")


@pytest.mark.asyncio
async def test_store_manager_async_methods() -> None:
    """Проверяет асинхронные методы StoreManager."""
    manager = StoreManager(backend=MemoryStore(), serializer="json")

    await manager.aset("async_key", {"status": "ok"})
    assert await manager.aexists("async_key")
    res = await manager.aget("async_key")
    assert res == {"status": "ok"}

    assert await manager.adelete("async_key")
    assert not await manager.aexists("async_key")
