from __future__ import annotations

import functools
import inspect
import time
from collections.abc import Callable
from typing import Any, TypeVar

import logging  # chutils: ignore[ChutilsIntegrationRule]

from chutils.telegram.access import _extract_user_info
from chutils.telegram.rate_limit import _extract_chat_id

F = TypeVar("F", bound=Callable[..., Any])
logger = logging.getLogger("chutils.telegram")


def _extract_update_id(args: tuple[Any, ...], kwargs: dict[str, Any]) -> int | str | None:
    """Извлекает update_id из события."""
    if "update_id" in kwargs:
        val = kwargs["update_id"]
        return val if isinstance(val, (int, str)) else None
    for arg in args:
        if hasattr(arg, "update_id"):
            val = getattr(arg, "update_id")
            return val if isinstance(val, (int, str)) else None
    return None


class trace_telegram_update:
    """Контекстный менеджер и декоратор трейсинга и логирования Telegram-апдейтов."""

    def __init__(self, event: Any = None, logger_instance: Any = None) -> None:
        """Инициализирует trace_telegram_update.

        Args:
            event: Входящее событие/апдейт Telegram.
            logger_instance: Опциональный кастомный логгер.
        """
        self.event = event
        self.logger = logger_instance or logger
        self.start_time: float = 0.0

    def __enter__(self) -> trace_telegram_update:
        self.start_time = time.perf_counter()
        uid, uname = _extract_user_info((self.event,), {}) if self.event else (None, None)
        cid = _extract_chat_id((self.event,), {}) if self.event else None
        upid = _extract_update_id((self.event,), {}) if self.event else None

        self.logger.debug(
            f"Processing Telegram update (user_id={uid}, chat_id={cid}, update_id={upid})"
        )
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        duration_ms = round((time.perf_counter() - self.start_time) * 1000, 2)
        if exc_val is not None:
            self.logger.error(
                f"Error processing Telegram update in {duration_ms}ms: {exc_val}",
                exc_info=(exc_type, exc_val, exc_tb),
            )
        else:
            self.logger.info(f"Telegram update processed successfully in {duration_ms}ms")

    async def __aenter__(self) -> trace_telegram_update:
        return self.__enter__()

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.__exit__(exc_type, exc_val, exc_tb)

    def __call__(self, func: F) -> F:
        """Оборачивает функцию декоратором трейсинга.

        Args:
            func: Целевая функция.

        Returns:
            Обернутая функция.
        """
        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                event = args[0] if args else kwargs.get("event")
                async with trace_telegram_update(event=event, logger_instance=self.logger):
                    return await func(*args, **kwargs)

            return async_wrapper  # type: ignore[return-value]
        else:

            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                event = args[0] if args else kwargs.get("event")
                with trace_telegram_update(event=event, logger_instance=self.logger):
                    return func(*args, **kwargs)

            return sync_wrapper  # type: ignore[return-value]
