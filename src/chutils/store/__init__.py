"""
Модуль chutils.store — Абстракция Key-Value хранилища.
"""
from __future__ import annotations

from .backends.base import BaseStoreBackend as BaseStoreBackend
from .backends.memory import MemoryStore as MemoryStore
from .manager import StoreManager as StoreManager

__all__ = ["BaseStoreBackend", "MemoryStore", "StoreManager"]
