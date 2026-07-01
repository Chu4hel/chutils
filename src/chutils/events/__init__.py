# -*- coding: utf-8 -*-
"""
Модуль шины событий (In-Memory Event Bus).

Предоставляет возможности подписки на события и публикации событий
как в синхронном, так и в асинхронном режимах.
"""

from .core import (
    EventBus as EventBus,
    ErrorStrategy as ErrorStrategy,
    subscribe as subscribe,
    publish as publish,
    publish_async as publish_async,
)

__all__ = [
    "EventBus",
    "ErrorStrategy",
    "subscribe",
    "publish",
    "publish_async",
]
