"""
Модуль шины событий (In-Memory Event Bus).

Предоставляет возможности подписки на события и публикации событий
как в синхронном, так и в асинхронном режимах.
"""

from .core import (
    ErrorStrategy as ErrorStrategy,
)
from .core import (
    EventBus as EventBus,
)
from .core import (
    publish as publish,
)
from .core import (
    publish_async as publish_async,
)
from .core import (
    subscribe as subscribe,
)

__all__ = [
    "ErrorStrategy",
    "EventBus",
    "publish",
    "publish_async",
    "subscribe",
]
