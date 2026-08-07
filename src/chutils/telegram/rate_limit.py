from __future__ import annotations

import functools
import inspect
import time
from collections.abc import Callable
from typing import Any, TypeVar

from chutils.exceptions.resilience import RateLimitExceededError
from chutils.telegram.access import _extract_user_info

F = TypeVar("F", bound=Callable[..., Any])


def _extract_chat_id(args: tuple[Any, ...], kwargs: dict[str, Any]) -> int | None:
    """Извлекает chat_id из аргументов вызова функции."""
    if "chat_id" in kwargs and isinstance(kwargs["chat_id"], int):
        return kwargs["chat_id"]
    if "chat" in kwargs and hasattr(kwargs["chat"], "id"):
        return getattr(kwargs["chat"], "id", None)

    for arg in args:
        if hasattr(arg, "chat") and getattr(arg, "chat", None) is not None:
            return getattr(arg.chat, "id", None)
        if hasattr(arg, "message") and getattr(arg, "message", None) is not None:
            msg = arg.message
            if hasattr(msg, "chat"):
                return getattr(msg.chat, "id", None)

    return None


class TelegramRateLimiter:
    """Движок ограничений вызовов (Rate Limiter) для Telegram-ботов."""

    def __init__(self, rate: int = 1, per: float = 1.0) -> None:
        """Инициализирует TelegramRateLimiter.

        Args:
            rate: Максимальное количество допустимых вызовов.
            per: Период времени в секундах.
        """
        self.rate = rate
        self.per = per
        self._calls: dict[str, list[float]] = {}

    def check_rate_limit(self, key: str) -> tuple[bool, float]:
        """Проверяет превышение лимита вызовов для ключа.

        Args:
            key: Уникальный идентификатор сущности (user_id / chat_id).

        Returns:
            Кортеж (is_limited, wait_sec), где is_limited - флаг превышения, wait_sec - секунд до разблокировки.
        """
        now = time.monotonic()
        history = self._calls.setdefault(key, [])
        # Очищаем устаревшие отметки времени
        history = [t for t in history if now - t < self.per]
        self._calls[key] = history

        if len(history) >= self.rate:
            oldest = history[0]
            wait_sec = max(0.0, self.per - (now - oldest))
            return True, round(wait_sec, 1)

        history.append(now)
        return False, 0.0


def tg_rate_limit(
    rate: int = 1,
    per: float = 1.0,
    scope: str = "user_id",
    warning_text: str | None = "⏱ Пожалуйста, подождите {wait_sec} сек. перед повторной отправкой.",
    silent: bool = False,
    raise_on_limit: bool = False,
) -> Callable[[F], F]:
    """Декоратор ограничения частоты запросов для Telegram-ботов.

    Args:
        rate: Количество разрешенных запросов.
        per: Временное окно в секундах.
        scope: Область ограничения: 'user_id', 'chat_id' или 'user_and_chat'.
        warning_text: Шаблон предупреждения. Поддерживает форматирование {wait_sec}.
        silent: Если True, отбрасывать запросы без вывода предупреждения.
        raise_on_limit: Если True, выбрасывать RateLimitExceededError при флуде.

    Returns:
        Обернутая функция-хэндлер.
    """
    limiter = TelegramRateLimiter(rate=rate, per=per)

    def decorator(func: F) -> F:
        def _get_key(args: tuple[Any, ...], kwargs: dict[str, Any]) -> str:
            uid, _ = _extract_user_info(args, kwargs)
            cid = _extract_chat_id(args, kwargs)

            if scope == "chat_id" and cid is not None:
                return f"chat_{cid}"
            if scope == "user_and_chat" and uid is not None and cid is not None:
                return f"uc_{uid}_{cid}"
            return f"user_{uid if uid is not None else 'unknown'}"

        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                key = _get_key(args, kwargs)
                is_limited, wait_sec = limiter.check_rate_limit(key)

                if is_limited:
                    if raise_on_limit:
                        raise RateLimitExceededError(
                            f"Telegram rate limit exceeded. Retry in {wait_sec}s"
                        )
                    if silent:
                        return None
                    if warning_text:
                        msg = warning_text.format(wait_sec=wait_sec)
                        for arg in args:
                            if hasattr(arg, "answer") and callable(arg.answer):
                                try:
                                    await arg.answer(msg)
                                    return None
                                except Exception:
                                    pass
                            elif hasattr(arg, "reply") and callable(arg.reply):
                                try:
                                    await arg.reply(msg)
                                    return None
                                except Exception:
                                    pass
                    return None
                return await func(*args, **kwargs)

            return async_wrapper  # type: ignore[return-value]
        else:

            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                key = _get_key(args, kwargs)
                is_limited, wait_sec = limiter.check_rate_limit(key)

                if is_limited:
                    if raise_on_limit:
                        raise RateLimitExceededError(
                            f"Telegram rate limit exceeded. Retry in {wait_sec}s"
                        )
                    if silent:
                        return None
                    if warning_text:
                        msg = warning_text.format(wait_sec=wait_sec)
                        for arg in args:
                            if hasattr(arg, "reply") and callable(arg.reply):
                                try:
                                    arg.reply(msg)
                                    return None
                                except Exception:
                                    pass
                    return None
                return func(*args, **kwargs)

            return sync_wrapper  # type: ignore[return-value]

    return decorator
