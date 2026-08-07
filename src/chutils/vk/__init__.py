"""Экспорт основного модуля chutils.vk."""

from chutils.vk.callback import VKCallbackError, VKCallbackRouter

__all__ = [
    "VKCallbackRouter",
    "VKCallbackError",
]
