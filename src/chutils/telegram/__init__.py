from __future__ import annotations  # chutils: ignore[ChutilsIntegrationRule]

from .access import admin_only, is_admin
from .aiogram import (
    AdminFilter,
    SecretUserFilter,
    TelegramLoggingMiddleware,
    TelegramThrottlingMiddleware,
)
from .formatting import escape_html, escape_markdown, smart_truncate, split_message
from .keyboard import PaginatorKeyboard, build_inline_keyboard
from .logging import trace_telegram_update  # chutils: ignore[ChutilsIntegrationRule]
from .media import download_user_file, send_telegram_file
from .notifier import HealthCheckAlertBridge, TelegramLogHandler, send_alert
from .rate_limit import TelegramRateLimiter, tg_rate_limit
from .whitelist import AccessListManager, allowed_only

__all__ = [
    "AccessListManager",
    "AdminFilter",
    "HealthCheckAlertBridge",
    "PaginatorKeyboard",
    "SecretUserFilter",
    "TelegramLogHandler",
    "TelegramLoggingMiddleware",
    "TelegramRateLimiter",
    "TelegramThrottlingMiddleware",
    "admin_only",
    "allowed_only",
    "build_inline_keyboard",
    "download_user_file",
    "escape_html",
    "escape_markdown",
    "is_admin",
    "send_alert",
    "send_telegram_file",
    "smart_truncate",
    "split_message",
    "tg_rate_limit",
    "trace_telegram_update",
]
