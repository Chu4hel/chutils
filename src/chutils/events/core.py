# -*- coding: utf-8 -*-
"""Ядро шины событий (In-Memory Event Bus)."""

import threading
import typing as t
from collections import defaultdict
from collections.abc import Callable

class EventBus:
    """Внутренняя шина событий (In-Memory Event Bus).

    Обеспечивает регистрацию подписчиков и публикацию событий.
    Потокобезопасна.
    """

    def __init__(self) -> None:
        """Инициализирует шину событий."""
        self._subscribers: dict[str, list[Callable[..., t.Any]]] = defaultdict(list)
        self._lock = threading.Lock()

    def subscribe(self, event_name: str) -> Callable[[Callable[..., t.Any]], Callable[..., t.Any]]:
        """Декоратор для регистрации обработчика события на данном инстансе шины.

        Args:
            event_name: Имя события, на которое подписывается обработчик.

        Returns:
            Декоратор, который регистрирует функцию-обработчик и возвращает её.
        """
        def decorator(func: Callable[..., t.Any]) -> Callable[..., t.Any]:
            with self._lock:
                if func not in self._subscribers[event_name]:
                    self._subscribers[event_name].append(func)
            return func
        return decorator

    def unsubscribe(self, event_name: str, func: Callable[..., t.Any]) -> None:
        """Отменяет подписку обработчика на событие.

        Args:
            event_name: Имя события.
            func: Функция-обработчик, которую нужно отписать.
        """
        with self._lock:
            if event_name in self._subscribers:
                try:
                    self._subscribers[event_name].remove(func)
                except ValueError:
                    pass


# Глобальный инстанс шины событий
_global_bus = EventBus()

def subscribe(event_name: str) -> Callable[[Callable[..., t.Any]], Callable[..., t.Any]]:
    """Декоратор для подписки на событие в глобальной шине.

    Args:
        event_name: Имя события.

    Returns:
        Декоратор для функции-обработчика.
    """
    return _global_bus.subscribe(event_name)
