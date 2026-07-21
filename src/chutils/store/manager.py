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


def _get_tracing() -> Any:
    try:
        from chutils import tracing

        return tracing
    except Exception:
        return None


def _get_metrics() -> Any:
    try:
        from chutils import metrics

        return metrics
    except Exception:
        return None


class JSONSerializer:
    """Сериализатор данных в формате JSON."""

    def dumps(self, value: Any) -> str:
        """Сериализует значение в JSON-строку.

        Args:
            value: Значение для сериализации.

        Returns:
            JSON строка.
        """
        return json.dumps(value, ensure_ascii=False)

    def loads(self, raw_value: str | bytes) -> Any:
        """Десериализует JSON значение.

        Args:
            raw_value: Исходное значение JSON.

        Returns:
            Десериализованный объект.
        """
        if isinstance(raw_value, bytes):
            raw_value = raw_value.decode("utf-8")
        return json.loads(raw_value)


class PickleSerializer:
    """Сериализатор данных в формате Pickle."""

    def dumps(self, value: Any) -> bytes:
        """Сериализует значение в байты Pickle.

        Args:
            value: Значение для сериализации.

        Returns:
            Сериализованные байты.
        """
        return pickle.dumps(value)

    def loads(self, raw_value: str | bytes) -> Any:
        """Десериализует значение Pickle.

        Args:
            raw_value: Исходные байты или строка.

        Returns:
            Десериализованный объект.
        """
        if isinstance(raw_value, str):
            raw_value = raw_value.encode("utf-8")
        return pickle.loads(raw_value)


class RawSerializer:
    """Пасс-через сериализатор без изменений."""

    def dumps(self, value: Any) -> Any:
        """Возвращает значение без изменений.

        Args:
            value: Исходное значение.

        Returns:
            То же значение.
        """
        return value

    def loads(self, raw_value: Any) -> Any:
        """Возвращает значение без изменений.

        Args:
            raw_value: Исходное значение.

        Returns:
            То же значение.
        """
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
        """Создает менеджер хранилища на основе конфигурационного словаря.

        Args:
            config: Словарь конфигурации.

        Returns:
            Новый экземпляр StoreManager.
        """
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
        tracing = _get_tracing()
        if tracing is not None and hasattr(tracing, "trace"):
            try:
                res = tracing.trace(f"store.{op}")
                if hasattr(res, "__enter__"):
                    return res
            except Exception:
                pass
        return nullcontext()

    def _record_metric(self, op: str, hit: bool | None = None) -> None:
        metrics = _get_metrics()
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
        """Извлекает и десериализует значение по ключу.

        Args:
            key: Ключ записи.
            default: Значение по умолчанию, если ключ не найден.

        Returns:
            Десериализованное значение или default.
        """
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
        """Сериализует и сохраняет значение по ключу.

        Args:
            key: Ключ записи.
            value: Значение для сохранения.
            ttl: Время жизни записи в секундах.

        Returns:
            True, если запись успешно сохранена.
        """
        with self._trace("set"):
            full_key = self._format_key(key)
            serialized_val = self._serializer.dumps(value)
            res = self._backend.set(full_key, serialized_val, ttl=ttl)
            self._record_metric("set")
            return res

    def delete(self, key: str) -> bool:
        """Удаляет запись по ключу.

        Args:
            key: Ключ записи.

        Returns:
            True, если ключ существовал и был удален.
        """
        with self._trace("delete"):
            full_key = self._format_key(key)
            res = self._backend.delete(full_key)
            self._record_metric("delete")
            return res

    def exists(self, key: str) -> bool:
        """Проверяет существование ключа.

        Args:
            key: Ключ записи.

        Returns:
            True, если ключ существует.
        """
        with self._trace("exists"):
            full_key = self._format_key(key)
            res = self._backend.exists(full_key)
            self._record_metric("exists")
            return res

    def clear(self) -> bool:
        """Очищает хранилище.

        Returns:
            True при успешной очистке.
        """
        with self._trace("clear"):
            res = self._backend.clear()
            self._record_metric("clear")
            return res

    async def aget(self, key: str, default: Any = None) -> Any:
        """Извлекает и десериализует значение по ключу (асинхронно).

        Args:
            key: Ключ записи.
            default: Значение по умолчанию, если ключ не найден.

        Returns:
            Десериализованное значение или default.
        """
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
        """Сериализует и сохраняет значение по ключу (асинхронно).

        Args:
            key: Ключ записи.
            value: Значение для сохранения.
            ttl: Время жизни записи в секундах.

        Returns:
            True, если запись успешно сохранена.
        """
        with self._trace("aset"):
            full_key = self._format_key(key)
            serialized_val = self._serializer.dumps(value)
            res = await self._backend.aset(full_key, serialized_val, ttl=ttl)
            self._record_metric("aset")
            return res

    async def adelete(self, key: str) -> bool:
        """Удаляет запись по ключу (асинхронно).

        Args:
            key: Ключ записи.

        Returns:
            True, если ключ существовал и был удален.
        """
        with self._trace("adelete"):
            full_key = self._format_key(key)
            res = await self._backend.adelete(full_key)
            self._record_metric("adelete")
            return res

    async def aexists(self, key: str) -> bool:
        """Проверяет существование ключа (асинхронно).

        Args:
            key: Ключ записи.

        Returns:
            True, если ключ существует.
        """
        with self._trace("aexists"):
            full_key = self._format_key(key)
            res = await self._backend.aexists(full_key)
            self._record_metric("aexists")
            return res

    async def aclear(self) -> bool:
        """Очищает хранилище (асинхронно).

        Returns:
            True при успешной очистке.
        """
        with self._trace("aclear"):
            res = await self._backend.aclear()
            self._record_metric("aclear")
            return res
