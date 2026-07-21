"""
Менеджер Key-Value хранилищ chutils.store с поддержкой сериализации, префиксов, метрик и трассировки.
"""
from __future__ import annotations

import json
import pickle
from contextlib import nullcontext
from typing import Any

from .backends.base import BaseStoreBackend
from .backends.memory import MemoryStore

try:
    from chutils import tracing
except Exception:
    tracing = None  # type: ignore[assignment]

try:
    from chutils import metrics
except Exception:
    metrics = None  # type: ignore[assignment]


class JSONSerializer:
    """Сериализатор данных в формате JSON."""

    def dumps(self, value: Any) -> str:
        return json.dumps(value, ensure_ascii=False)

    def loads(self, raw_value: str | bytes) -> Any:
        if isinstance(raw_value, bytes):
            raw_value = raw_value.decode("utf-8")
        return json.loads(raw_value)


class PickleSerializer:
    """Сериализатор данных в формате Pickle."""

    def dumps(self, value: Any) -> bytes:
        return pickle.dumps(value)

    def loads(self, raw_value: str | bytes) -> Any:
        if isinstance(raw_value, str):
            raw_value = raw_value.encode("utf-8")
        return pickle.loads(raw_value)


class RawSerializer:
    """Пасс-через сериализатор без изменений."""

    def dumps(self, value: Any) -> Any:
        return value

    def loads(self, raw_value: Any) -> Any:
        return raw_value


def _get_serializer(serializer_type: str | Any) -> Any:
    if hasattr(serializer_type, "dumps") and hasattr(serializer_type, "loads"):
        return serializer_type

    if isinstance(serializer_type, str):
        name = serializer_type.lower()
        if name == "json":
            return JSONSerializer()
        elif name == "pickle":
            return PickleSerializer()
        elif name in ("raw", "none", "passthrough"):
            return RawSerializer()

    return JSONSerializer()


class StoreManager:
    """Центральный менеджер Key-Value хранилища."""

    def __init__(
        self,
        backend: BaseStoreBackend | None = None,
        serializer: str | Any = "json",
        prefix: str = "",
    ) -> None:
        self._backend: BaseStoreBackend = backend or MemoryStore()
        self._serializer = _get_serializer(serializer)
        self._prefix = prefix

    @classmethod
    def from_config(cls, config: dict[str, Any] | None = None) -> StoreManager:
        """Создает менеджер хранилища на основе конфигурационного словаря."""
        cfg = config or {}
        backend_type = str(cfg.get("backend", "memory")).lower()
        serializer_type = cfg.get("serializer", "json")
        prefix = str(cfg.get("prefix", ""))

        backend: BaseStoreBackend
        if backend_type == "memory":
            backend = MemoryStore()
        elif backend_type == "redis":
            from .backends.redis import RedisStore

            url = str(cfg.get("url", "redis://localhost:6379/0"))
            backend = RedisStore(url=url)
        elif backend_type == "memcached":
            from .backends.memcached import MemcachedStore

            host = str(cfg.get("host", "127.0.0.1"))
            port = int(cfg.get("port", 11211))
            backend = MemcachedStore(host=host, port=port)
        else:
            backend = MemoryStore()

        return cls(backend=backend, serializer=serializer_type, prefix=prefix)

    def _format_key(self, key: str) -> str:
        return f"{self._prefix}{key}" if self._prefix else key

    def _trace(self, op: str) -> Any:
        if tracing is not None and hasattr(tracing, "trace"):
            try:
                res = tracing.trace(f"store.{op}")
                if hasattr(res, "__enter__"):
                    return res
            except Exception:
                pass
        return nullcontext()

    def _record_metric(self, op: str, hit: bool | None = None) -> None:
        if metrics is not None:
            try:
                if hasattr(metrics, "counter"):
                    metrics.counter("store_operations_total", labels={"op": op})
                    if hit is not None:
                        status = "hit" if hit else "miss"
                        metrics.counter("store_requests_total", labels={"status": status})
            except Exception:
                pass

    def get(self, key: str, default: Any = None) -> Any:
        """Извлекает и десериализует значение по ключу."""
        with self._trace("get"):
            full_key = self._format_key(key)
            raw_val = self._backend.get(full_key, default=None)
            if raw_val is None:
                self._record_metric("get", hit=False)
                return default
            try:
                val = self._serializer.loads(raw_val)
                self._record_metric("get", hit=True)
                return val
            except Exception:
                self._record_metric("get", hit=False)
                return default

    def set(self, key: str, value: Any, ttl: int | float | None = None) -> bool:
        """Сериализует и сохраняет значение по ключу."""
        with self._trace("set"):
            full_key = self._format_key(key)
            serialized_val = self._serializer.dumps(value)
            res = self._backend.set(full_key, serialized_val, ttl=ttl)
            self._record_metric("set")
            return res

    def delete(self, key: str) -> bool:
        """Удаляет запись по ключу."""
        with self._trace("delete"):
            full_key = self._format_key(key)
            res = self._backend.delete(full_key)
            self._record_metric("delete")
            return res

    def exists(self, key: str) -> bool:
        """Проверяет существование ключа."""
        with self._trace("exists"):
            full_key = self._format_key(key)
            res = self._backend.exists(full_key)
            self._record_metric("exists")
            return res

    def clear(self) -> bool:
        """Очищает хранилище."""
        with self._trace("clear"):
            res = self._backend.clear()
            self._record_metric("clear")
            return res

    async def aget(self, key: str, default: Any = None) -> Any:
        """Извлекает и десериализует значение по ключу (асинхронно)."""
        with self._trace("aget"):
            full_key = self._format_key(key)
            raw_val = await self._backend.aget(full_key, default=None)
            if raw_val is None:
                self._record_metric("aget", hit=False)
                return default
            try:
                val = self._serializer.loads(raw_val)
                self._record_metric("aget", hit=True)
                return val
            except Exception:
                self._record_metric("aget", hit=False)
                return default

    async def aset(self, key: str, value: Any, ttl: int | float | None = None) -> bool:
        """Сериализует и сохраняет значение по ключу (асинхронно)."""
        with self._trace("aset"):
            full_key = self._format_key(key)
            serialized_val = self._serializer.dumps(value)
            res = await self._backend.aset(full_key, serialized_val, ttl=ttl)
            self._record_metric("aset")
            return res

    async def adelete(self, key: str) -> bool:
        """Удаляет запись по ключу (асинхронно)."""
        with self._trace("adelete"):
            full_key = self._format_key(key)
            res = await self._backend.adelete(full_key)
            self._record_metric("adelete")
            return res

    async def aexists(self, key: str) -> bool:
        """Проверяет существование ключа (асинхронно)."""
        with self._trace("aexists"):
            full_key = self._format_key(key)
            res = await self._backend.aexists(full_key)
            self._record_metric("aexists")
            return res

    async def aclear(self) -> bool:
        """Очищает хранилище (асинхронно)."""
        with self._trace("aclear"):
            res = await self._backend.aclear()
            self._record_metric("aclear")
            return res
