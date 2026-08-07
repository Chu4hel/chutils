from __future__ import annotations  # chutils: ignore[ChutilsIntegrationRule]

from .access import is_admin, admin_only
from .aiogram import AdminFilter, SecretUserFilter, TelegramThrottlingMiddleware, TelegramLoggingMiddleware
from .formatting import escape_markdown, escape_html, smart_truncate, split_message
from .keyboard import build_inline_keyboard, PaginatorKeyboard
from .logging import trace_telegram_update  # chutils: ignore[ChutilsIntegrationRule]
from .notifier import TelegramLogHandler, HealthCheckAlertBridge, send_alert
from .rate_limit import TelegramRateLimiter, tg_rate_limit
from .whitelist import AccessListManager, allowed_only

from .media import download_user_file

__all__ = [
    "download_user_file",
    "is_admin",
    "admin_only",
    "AdminFilter",
    "SecretUserFilter",
    "TelegramRateLimiter",
    "tg_rate_limit",
    "TelegramThrottlingMiddleware",
    "TelegramLoggingMiddleware",
    "AccessListManager",
    "allowed_only",
    "trace_telegram_update",
    "escape_markdown",
    "escape_html",
    "smart_truncate",
    "split_message",
    "TelegramLogHandler",
    "HealthCheckAlertBridge",
    "send_alert",
    "build_inline_keyboard",
    "PaginatorKeyboard",
]
