"""
Высокоуровневый API журнала аудита: декоратор @audit_event и контекстный менеджер audit_context.

Примеры:
    Декоратор синхронной функции::

        backend = FileBackend("audit.jsonl")

        @audit_event(action="user.login", actor="system", backend=backend)
        def login(user_id: str) -> None:
            ...

    Декоратор асинхронной функции::

        @audit_event(action="db.write", actor=lambda *a, **kw: kw.get("user"), backend=backend)
        async def save(user: str, data: dict) -> None:
            ...

    Контекстный менеджер::

        with audit_context(action="batch.process", actor="worker", backend=backend) as ctx:
            ctx.details["count"] = process_records()
"""
from __future__ import annotations

import asyncio
import functools
from collections.abc import Callable, Generator
from contextlib import contextmanager
from typing import Union


# ---------------------------------------------------------------------------
# Вспомогательный класс контекста
# ---------------------------------------------------------------------------


class _AuditContextState:
    """Изменяемый контейнер для данных события внутри audit_context.

    Attributes:
        status: Итоговый статус события ('success' / 'failed').
        details: Произвольные детали события.
    """

    def __init__(self) -> None:
        self.status: str = "success"
        self.details: dict[str, object] = {}


# ---------------------------------------------------------------------------
# audit_context — контекстный менеджер
# ---------------------------------------------------------------------------


@contextmanager
def audit_context(
        action: str,
        actor: str,
        *,
        target: str | None = None,
        backend: object,
) -> Generator[_AuditContextState, None, None]:
    """Контекстный менеджер для регистрации события аудита в блоке кода.

    При нормальном завершении блока записывает status='success'.
    При исключении — status='failed' с информацией об ошибке в details.
    Исключение всегда пробрасывается вверх.

    Args:
        action: Название операции.
        actor: Субъект действия.
        target: Объект операции (опционально).
        backend: Экземпляр BaseAuditBackend для записи события.

    Yields:
        _AuditContextState: Объект с изменяемыми полями status и details.

    Example:
        with audit_context(action="order.pay", actor="user_1", backend=backend) as ctx:
            ctx.details["amount"] = 100
    """
    ctx = _AuditContextState()
    try:
        yield ctx
    except Exception as exc:
        ctx.status = "failed"
        ctx.details.setdefault("error_type", type(exc).__name__)
        ctx.details.setdefault("error_message", str(exc))
        raise
    finally:
        backend.log(  # type: ignore[attr-defined]
            action=action,
            actor=actor,
            target=target,
            status=ctx.status,
            details=ctx.details,
        )


# ---------------------------------------------------------------------------
# audit_event — декоратор
# ---------------------------------------------------------------------------

_ActorOrCallable = Union[str, Callable[..., str]]
_TargetOrCallable = Union[str, Callable[..., str], None]


def audit_event(
        action: str,
        actor: _ActorOrCallable = "system",
        *,
        target: _TargetOrCallable = None,
        backend: object,
) -> Callable:  # type: ignore[type-arg]
    """Декоратор для автоматической регистрации события аудита при вызове функции.

    Работает с синхронными и асинхронными функциями. При успешном завершении
    записывает status='success', при исключении — status='failed' с деталями ошибки.
    Исключение всегда пробрасывается вверх.

    Args:
        action: Название операции (например, 'user.login').
        actor: Субъект действия — строка или callable(*args, **kwargs) -> str.
        target: Объект операции — строка, callable или None.
        backend: Экземпляр BaseAuditBackend для записи события.

    Returns:
        Декоратор, оборачивающий функцию.

    Example:
        @audit_event(action="user.delete", actor=lambda *a, **kw: kw["user_id"], backend=backend)
        def delete_user(user_id: str) -> None:
            ...
    """

    def decorator(func: Callable) -> Callable:  # type: ignore[type-arg]
        @functools.wraps(func)
        def sync_wrapper(*args: object, **kwargs: object) -> object:
            resolved_actor = actor(*args, **kwargs) if callable(actor) else actor
            resolved_target: str | None = (
                target(*args, **kwargs) if callable(target) else target
            )
            status = "success"
            details: dict[str, object] = {}
            try:
                return func(*args, **kwargs)
            except Exception as exc:
                status = "failed"
                details["error_type"] = type(exc).__name__
                details["error_message"] = str(exc)
                raise
            finally:
                backend.log(  # type: ignore[attr-defined]
                    action=action,
                    actor=resolved_actor,
                    target=resolved_target,
                    status=status,
                    details=details,
                )

        @functools.wraps(func)
        async def async_wrapper(*args: object, **kwargs: object) -> object:
            resolved_actor = actor(*args, **kwargs) if callable(actor) else actor
            resolved_target = (
                target(*args, **kwargs) if callable(target) else target
            )
            status = "success"
            details: dict[str, object] = {}
            try:
                return await func(*args, **kwargs)
            except Exception as exc:
                status = "failed"
                details["error_type"] = type(exc).__name__
                details["error_message"] = str(exc)
                raise
            finally:
                backend.log(  # type: ignore[attr-defined]
                    action=action,
                    actor=resolved_actor,
                    target=resolved_target,
                    status=status,
                    details=details,
                )

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


__all__ = ["audit_event", "audit_context"]
