"""Экспорт интеграций web-фреймворков для VKMA."""

from chutils.vkma.integrations.aiohttp import vkma_auth_middleware
from chutils.vkma.integrations.fastapi import VKMAAuthMiddleware, get_current_vkma_params
from chutils.vkma.integrations.flask import require_vkma_auth

__all__ = [
    "VKMAAuthMiddleware",
    "get_current_vkma_params",
    "require_vkma_auth",
    "vkma_auth_middleware",
]
