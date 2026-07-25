"""
Модуль типизированных сигналов, авто-связывания и безопасных слотов для Qt.
"""

from __future__ import annotations

import functools
import logging
from typing import Any, Callable, Generic, TypeVar, ParamSpec

from .shim import Signal, require_qt

P = ParamSpec("P")
T = TypeVar("T")


class BoundTypedSignal(Generic[P]):
    """Связанный типизированный сигнал Qt с точной типизацией connect и emit."""

    def __init__(self, raw_signal: Any) -> None:
        """Инициализирует связанный сигнал.

        Args:
            raw_signal: Нативный сигнал PyQt6 / PySide6.
        """
        self._raw_signal = raw_signal

    def connect(self, slot: Callable[P, Any]) -> Any:
        """Подключает слот к сигналу.

        Args:
            slot: Функция-обработчик сигналов.
        """
        if hasattr(self._raw_signal, "connect"):
            return self._raw_signal.connect(slot)
        return None

    def disconnect(self, slot: Callable[P, Any] | None = None) -> Any:
        """Отключает слот от сигнала.

        Args:
            slot: Опциональная функция-обработчик.
        """
        if hasattr(self._raw_signal, "disconnect"):
            if slot is not None:
                return self._raw_signal.disconnect(slot)
            return self._raw_signal.disconnect()
        return None

    def emit(self, *args: P.args, **kwargs: P.kwargs) -> None:
        """Излучает сигнал с переданными аргументами.

        Args:
            *args: Позиционные аргументы.
            **kwargs: Именованные аргументы.
        """
        if hasattr(self._raw_signal, "emit"):
            self._raw_signal.emit(*args, **kwargs)


class TypedSignal(Generic[P]):
    """Дескриптор типизированного сигнала для Qt классов."""

    def __init__(self, *types: type) -> None:
        """Инициализирует типизированный сигнал.

        Args:
            *types: Типы передаваемых сигналом аргументов.
        """
        require_qt()
        self.types = types
        self._underlying_signal = Signal(*types) if Signal is not None else None

    def __get__(self, instance: Any, owner: type | None = None) -> BoundTypedSignal[P] | TypedSignal[P]:
        if instance is None:
            return self

        try:
            cache = getattr(instance, "_typed_signals_cache", None)
            if cache is None:
                cache = {}
                setattr(instance, "_typed_signals_cache", cache)

            if id(self) in cache:
                return cache[id(self)]

            bound = BoundTypedSignal[P](self._underlying_signal)
            cache[id(self)] = bound
            return bound
        except AttributeError:
            return BoundTypedSignal[P](self._underlying_signal)


def qt_slot(
        *types: type,
        catch_exceptions: bool = True,
        logger_name: str | None = None,
) -> Callable[[Callable[P, T]], Callable[P, T | None]]:
    """Декоратор для безопасных слотов Qt с автоматическим логированием ошибок.

    Args:
        *types: Типы аргументов слота Qt.
        catch_exceptions: Перехватывать ли исключения.
        logger_name: Имя логгера для фиксации ошибок.

    Returns:
        Декорированная функция-слот.
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T | None]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T | None:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger = logging.getLogger(logger_name or func.__module__)
                logger.error(
                    "Исключение в Qt слоте %s: %s",
                    func.__qualname__,
                    e,
                    exc_info=True,
                )
                if not catch_exceptions:
                    raise
                return None

        return wrapper

    return decorator


def bind_qt_signals(instance: Any, bind_by_signature: bool = False) -> int:
    """Автоматически связывает сигналы объекта со слотами по соглашению об именовании `on_<signal_name>`.

    Args:
        instance: Экземпляр QObject или любого класса с сигналами и слотами.
        bind_by_signature: Включить ли экспериментальное связывание по совпадению типов.

    Returns:
        Количество успешно подключенных сигналов.
    """
    connected_count = 0

    # Ищем сигналы в экземпляре
    for attr_name in dir(instance):
        if attr_name.startswith("_"):
            continue

        try:
            attr_val = getattr(instance, attr_name)
        except Exception:
            continue

        # Проверяем, является ли атрибут сигналом Qt или TypedSignal
        is_signal = (
                isinstance(attr_val, BoundTypedSignal)
                or (hasattr(attr_val, "connect") and hasattr(attr_val, "emit"))
        )

        if not is_signal:
            continue

        # Ищем соответствующий слот on_<signal_name>
        target_slot_name = f"on_{attr_name}"
        if hasattr(instance, target_slot_name):
            slot = getattr(instance, target_slot_name)
            if callable(slot):
                attr_val.connect(slot)
                connected_count += 1

    return connected_count


class AutoBindMixin:
    """Миксин для автоматического подключения сигналов в __init__."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        bind_qt_signals(self)
