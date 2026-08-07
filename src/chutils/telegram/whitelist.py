from __future__ import annotations

import functools
import inspect
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

from chutils.config import get_config_value
from chutils.exceptions.telegram import TelegramAccessDeniedError
from chutils.fs import atomic_write
from chutils.telegram.access import _extract_user_info

F = TypeVar("F", bound=Callable[..., Any])


class AccessListManager:
    """Менеджер белых и черных списков пользователей Telegram."""

    def __init__(
        self,
        storage_path: str | Path | None = None,
        allowed_ids: list[int] | None = None,
        allowed_usernames: list[str] | None = None,
        blocked_ids: list[int] | None = None,
        blocked_usernames: list[str] | None = None,
    ) -> None:
        """Инициализирует AccessListManager.

        Args:
            storage_path: Опциональный путь к JSON-файлу для автосохранения списков.
            allowed_ids: Начальный белый список Telegram ID.
            allowed_usernames: Начальный белый список юзернеймов.
            blocked_ids: Начальный черный список Telegram ID.
            blocked_usernames: Начальный черный список юзернеймов.
        """
        self.storage_path = Path(storage_path).resolve() if storage_path else None
        self.allowed_ids: set[int] = set(allowed_ids or [])
        self.allowed_usernames: set[str] = {u.lstrip("@").lower() for u in (allowed_usernames or [])}
        self.blocked_ids: set[int] = set(blocked_ids or [])
        self.blocked_usernames: set[str] = {u.lstrip("@").lower() for u in (blocked_usernames or [])}

        if self.storage_path and self.storage_path.exists():
            self.load()
        else:
            # Fallback на конфигурацию
            self._load_from_config()

    def _load_from_config(self) -> None:
        """Считывает настройки списков из конфигурации chutils, если списки пусты."""
        if not self.allowed_ids and not self.allowed_usernames:
            cfg_allowed = get_config_value("Telegram", "allowed_users", None)
            if isinstance(cfg_allowed, (list, tuple)):
                for val in cfg_allowed:
                    if isinstance(val, int) or (isinstance(val, str) and val.isdigit()):
                        self.allowed_ids.add(int(val))
                    elif isinstance(val, str):
                        self.allowed_usernames.add(val.lstrip("@").lower())

        if not self.blocked_ids and not self.blocked_usernames:
            cfg_blocked = get_config_value("Telegram", "blocked_users", None)
            if isinstance(cfg_blocked, (list, tuple)):
                for val in cfg_blocked:
                    if isinstance(val, int) or (isinstance(val, str) and val.isdigit()):
                        self.blocked_ids.add(int(val))
                    elif isinstance(val, str):
                        self.blocked_usernames.add(val.lstrip("@").lower())

    def is_user_allowed(self, user_id: int | None = None, username: str | None = None) -> bool:
        """Проверяет разрешения для пользователя.

        Args:
            user_id: Telegram ID пользователя.
            username: Username пользователя.

        Returns:
            True, если пользователь имеет доступ, иначе False.
        """
        clean_uname = username.lstrip("@").lower() if username else None

        # Проверка черного списка
        if user_id is not None and user_id in self.blocked_ids:
            return False
        if clean_uname and clean_uname in self.blocked_usernames:
            return False

        # Если белый список пуст, доступ разрешен всем (кроме заблокированных)
        if not self.allowed_ids and not self.allowed_usernames:
            return True

        # Проверка белого списка
        if user_id is not None and user_id in self.allowed_ids:
            return True
        if clean_uname and clean_uname in self.allowed_usernames:
            return True

        return False

    def allow_user(self, user_id_or_username: int | str) -> None:
        """Добавляет пользователя в белый список и убирает из черного.

        Args:
            user_id_or_username: ID пользователя Telegram или его юзернейм.
        """
        if isinstance(user_id_or_username, int) or str(user_id_or_username).isdigit():
            uid = int(user_id_or_username)
            self.allowed_ids.add(uid)
            self.blocked_ids.discard(uid)
        else:
            uname = str(user_id_or_username).lstrip("@").lower()
            self.allowed_usernames.add(uname)
            self.blocked_usernames.discard(uname)

        if self.storage_path:
            self.save()

    def block_user(self, user_id_or_username: int | str) -> None:
        """Добавляет пользователя в черный список и убирает из белого.

        Args:
            user_id_or_username: ID пользователя Telegram или его юзернейм.
        """
        if isinstance(user_id_or_username, int) or str(user_id_or_username).isdigit():
            uid = int(user_id_or_username)
            self.blocked_ids.add(uid)
            self.allowed_ids.discard(uid)
        else:
            uname = str(user_id_or_username).lstrip("@").lower()
            self.blocked_usernames.add(uname)
            self.allowed_usernames.discard(uname)

        if self.storage_path:
            self.save()

    def remove_user(self, user_id_or_username: int | str) -> None:
        """Удаляет пользователя из белого и черного списков.

        Args:
            user_id_or_username: ID пользователя Telegram или его юзернейм.
        """
        if isinstance(user_id_or_username, int) or str(user_id_or_username).isdigit():
            uid = int(user_id_or_username)
            self.allowed_ids.discard(uid)
            self.blocked_ids.discard(uid)
        else:
            uname = str(user_id_or_username).lstrip("@").lower()
            self.allowed_usernames.discard(uname)
            self.blocked_usernames.discard(uname)

        if self.storage_path:
            self.save()

    def save(self) -> None:
        """Атомарно сохраняет списки в JSON-файл."""
        if not self.storage_path:
            return
        data = {
            "allowed_ids": list(self.allowed_ids),
            "allowed_usernames": list(self.allowed_usernames),
            "blocked_ids": list(self.blocked_ids),
            "blocked_usernames": list(self.blocked_usernames),
        }
        content = json.dumps(data, indent=2, ensure_ascii=False)
        atomic_write(self.storage_path, content, encoding="utf-8")

    def load(self) -> None:
        """Загружает списки из JSON-файла."""
        if not self.storage_path or not self.storage_path.exists():
            return
        try:
            content = self.storage_path.read_text(encoding="utf-8")
            data = json.loads(content)
            self.allowed_ids = set(data.get("allowed_ids", []))
            self.allowed_usernames = set(data.get("allowed_usernames", []))
            self.blocked_ids = set(data.get("blocked_ids", []))
            self.blocked_usernames = set(data.get("blocked_usernames", []))
        except Exception:
            pass


def allowed_only(
    manager: AccessListManager | None = None,
    allowed_ids: list[int] | None = None,
    allowed_usernames: list[str] | None = None,
    blocked_ids: list[int] | None = None,
    blocked_usernames: list[str] | None = None,
    refusal_text: str | None = "⛔ У вас нет доступа к этой функции",
    silent: bool = False,
    raise_on_denied: bool = False,
) -> Callable[[F], F]:
    """Декоратор ограничения доступа по белым и черным спискам.

    Args:
        manager: Готовый экземпляр AccessListManager.
        allowed_ids: Белый список Telegram ID.
        allowed_usernames: Белый список юзернеймов.
        blocked_ids: Черный список Telegram ID.
        blocked_usernames: Черный список юзернеймов.
        refusal_text: Сообщение об отказе.
        silent: Если True, отбрасывать запросы без вывода ответа.
        raise_on_denied: Если True, выбрасывать TelegramAccessDeniedError.

    Returns:
        Обернутая функция.
    """
    mgr = manager or AccessListManager(
        allowed_ids=allowed_ids,
        allowed_usernames=allowed_usernames,
        blocked_ids=blocked_ids,
        blocked_usernames=blocked_usernames,
    )

    def decorator(func: F) -> F:
        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                uid, uname = _extract_user_info(args, kwargs)
                if not mgr.is_user_allowed(uid, uname):
                    if raise_on_denied:
                        raise TelegramAccessDeniedError("Access denied by whitelist/blacklist", user_id=uid)
                    if silent:
                        return None
                    if refusal_text:
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
                if not mgr.is_user_allowed(uid, uname):
                    if raise_on_denied:
                        raise TelegramAccessDeniedError("Access denied by whitelist/blacklist", user_id=uid)
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
