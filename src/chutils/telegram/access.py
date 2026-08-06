from __future__ import annotations

import functools
import inspect
from collections.abc import Callable
from typing import Any, TypeVar

from chutils.config import get_config_value
from chutils.exceptions.telegram import TelegramAccessDeniedError

F = TypeVar("F", bound=Callable[..., Any])


def _extract_user_info(args: tuple[Any, ...], kwargs: dict[str, Any]) -> tuple[int | None, str | None]:
    """Извлекает user_id и username из аргументов вызова функции."""
    # Прямые аргументы
    if "user_id" in kwargs or "username" in kwargs:
        uid = kwargs.get("user_id") if isinstance(kwargs.get("user_id"), int) else None
        uname = kwargs.get("username") if isinstance(kwargs.get("username"), str) else None
        if uid is not None or uname is not None:
            return uid, uname
    if "from_user" in kwargs and hasattr(kwargs["from_user"], "id"):
        user = kwargs["from_user"]
        return getattr(user, "id", None), getattr(user, "username", None)

    # Ищем объективные сущности в позиционных аргументах (aiogram, telebot, python-telegram-bot)
    for arg in args:
        if hasattr(arg, "from_user") and getattr(arg, "from_user", None) is not None:
            user = arg.from_user
            return getattr(user, "id", None), getattr(user, "username", None)
        if hasattr(arg, "user") and getattr(arg, "user", None) is not None:
            user = arg.user
            return getattr(user, "id", None), getattr(user, "username", None)
        if hasattr(arg, "effective_user") and getattr(arg, "effective_user", None) is not None:
            user = arg.effective_user
            return getattr(user, "id", None), getattr(user, "username", None)
        if hasattr(arg, "id") and isinstance(arg.id, int) and (hasattr(arg, "is_bot") or hasattr(arg, "first_name")):
            return arg.id, getattr(arg, "username", None)

    return None, None


def is_admin(
    user_id: int | None = None,
    username: str | None = None,
    admin_ids: list[int] | None = None,
    admin_usernames: list[str] | None = None,
    is_admin_func: Callable[[int | None, str | None], bool] | None = None,
) -> bool:
    """Проверяет, является ли пользователь администратором.

    Если явные списки `admin_ids` / `admin_usernames` не заданы, считывает
    их из конфигурации `chutils` (секция 'Telegram', ключи 'admin_ids' / 'admin_usernames').

    Args:
        user_id: Telegram ID пользователя.
        username: Telegram username пользователя.
        admin_ids: Список разрешенных Telegram ID администраторов.
        admin_usernames: Список разрешенных username администраторов.
        is_admin_func: Кастомный предикат проверки.

    Returns:
        True, если пользователь является администратором, иначе False.
    """
    if is_admin_func is not None:
        return is_admin_func(user_id, username)

    # Загружаем из конфигурации, если параметры не переданы
    if admin_ids is None:
        cfg_ids = get_config_value("Telegram", "admin_ids", None)
        if isinstance(cfg_ids, (list, tuple)):
            admin_ids = [int(x) for x in cfg_ids if str(x).isdigit() or isinstance(x, int)]
        elif isinstance(cfg_ids, str):
            admin_ids = [int(x.strip()) for x in cfg_ids.split(",") if x.strip().isdigit()]

    if admin_usernames is None:
        cfg_names = get_config_value("Telegram", "admin_usernames", None)
        if isinstance(cfg_names, (list, tuple)):
            admin_usernames = [str(x).strip().lstrip("@").lower() for x in cfg_names if x]
        elif isinstance(cfg_names, str):
            admin_usernames = [x.strip().lstrip("@").lower() for x in cfg_names.split(",") if x.strip()]

    if user_id is not None and admin_ids and user_id in admin_ids:
        return True

    if username is not None and admin_usernames:
        clean_name = username.lstrip("@").lower()
        if clean_name in [u.lstrip("@").lower() for u in admin_usernames]:
            return True

    return False


def admin_only(
    admin_ids: list[int] | None = None,
    admin_usernames: list[str] | None = None,
    is_admin_func: Callable[[int | None, str | None], bool] | None = None,
    refusal_text: str | None = "⛔ Доступ запрещен: требуется статус администратора",
    silent: bool = False,
    raise_on_denied: bool = False,
) -> Callable[[F], F]:
    """Декоратор для ограничения доступа к синхронным и асинхронным хэндлерам Telegram-ботов.

    Args:
        admin_ids: Разрешенные Telegram ID.
        admin_usernames: Разрешенные юзернеймы.
        is_admin_func: Кастомный предикат проверки.
        refusal_text: Текст сообщения при отказе в доступе.
        silent: Если True, тихо игнорировать неавторизованные запросы.
        raise_on_denied: Если True, выбрасывать TelegramAccessDeniedError.

    Returns:
        Обернутый хэндлер.
    """

    def decorator(func: F) -> F:
        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                uid, uname = _extract_user_info(args, kwargs)
                if not is_admin(uid, uname, admin_ids, admin_usernames, is_admin_func):
                    if raise_on_denied:
                        raise TelegramAccessDeniedError(user_id=uid)
                    if silent:
                        return None
                    if refusal_text:
                        # Попытка ответить на event/message при наличии метода answer или reply
                        for arg in args:
                            if hasattr(arg, "answer") and callable(arg.answer):
                                try:
                                    await arg.answer(refusal_text)
                                    return None
                                except Exception:
                                    pass
                            elif hasattr(arg, "reply") and callable(arg.reply):
                                try:
                                    await arg.reply(refusal_text)
                                    return None
                                except Exception:
                                    pass
                    return None
                return await func(*args, **kwargs)

            return async_wrapper  # type: ignore[return-value]
        else:

            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                uid, uname = _extract_user_info(args, kwargs)
                if not is_admin(uid, uname, admin_ids, admin_usernames, is_admin_func):
                    if raise_on_denied:
                        raise TelegramAccessDeniedError(user_id=uid)
                    if silent:
                        return None
                    if refusal_text:
                        for arg in args:
                            if hasattr(arg, "reply") and callable(arg.reply):
                                try:
                                    arg.reply(refusal_text)
                                    return None
                                except Exception:
                                    pass
                    return None
                return func(*args, **kwargs)

            return sync_wrapper  # type: ignore[return-value]

    return decorator
