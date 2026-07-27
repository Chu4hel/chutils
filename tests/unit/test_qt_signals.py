"""
Тесты для типизированных сигналов и авто-связывания (src/chutils/qt/signals.py).
"""

from unittest.mock import MagicMock, patch

import pytest

import chutils.qt.shim as shim
from chutils.exceptions import OptionalDependencyError


def test_typed_signal_without_qt() -> None:
    """Проверяет выбрасывание OptionalDependencyError при отсутствии Qt."""
    err = OptionalDependencyError("Библиотека PyQt6 или PySide6 не установлена.", dependency="qt")
    with patch.object(shim, "QT_BINDING", None), patch("chutils.qt.signals.require_qt", side_effect=err):
        from chutils.qt.signals import TypedSignal
        with pytest.raises(OptionalDependencyError):
            TypedSignal(str)



def test_bound_typed_signal_operations() -> None:
    """Проверяет вызовы методов connect, disconnect и emit на BoundTypedSignal."""
    mock_raw = MagicMock()
    from chutils.qt.signals import BoundTypedSignal

    bound = BoundTypedSignal[tuple[str]](mock_raw)

    handler = lambda msg: None
    bound.connect(handler)
    mock_raw.connect.assert_called_once_with(handler)

    bound.emit("hello")
    mock_raw.emit.assert_called_once_with("hello")

    bound.disconnect(handler)
    mock_raw.disconnect.assert_called_once_with(handler)


def test_bind_qt_signals_auto_binding() -> None:
    """Проверяет автоматическое подключение сигнала к слоту по имени on_<signal_name>."""

    class DummyComponent:
        def __init__(self) -> None:
            self.data_loaded = MagicMock()
            self.data_loaded.connect = MagicMock()
            self.data_loaded.emit = MagicMock()

        def on_data_loaded(self, data: str) -> None:
            pass

    component = DummyComponent()
    with patch("chutils.qt.signals.require_qt"):
        from chutils.qt.signals import bind_qt_signals
        count = bind_qt_signals(component)
        assert count == 1
        component.data_loaded.connect.assert_called_once_with(component.on_data_loaded)


def test_auto_bind_mixin() -> None:
    """Проверяет автоматическое вызов bind_qt_signals в AutoBindMixin."""

    class MyWidget:
        def __init__(self) -> None:
            self.clicked = MagicMock()
            self.clicked.connect = MagicMock()
            self.clicked.emit = MagicMock()

        def on_clicked(self) -> None:
            pass

    class MyBoundWidget(MyWidget):
        def __init__(self) -> None:
            super().__init__()
            from chutils.qt.signals import bind_qt_signals
            bind_qt_signals(self)

    widget = MyBoundWidget()
    widget.clicked.connect.assert_called_once_with(widget.on_clicked)


def test_qt_slot_decorator_raise_exception() -> None:
    """Проверяет проброс исключения, если catch_exceptions=False."""
    from chutils.qt.signals import qt_slot

    @qt_slot(catch_exceptions=False)
    def reraising_slot() -> None:
        raise ValueError("Reraised Error")

    with pytest.raises(ValueError, match="Reraised Error"):
        reraising_slot()


def test_typed_signal_descriptor_access() -> None:
    """Проверяет получение дескриптора TypedSignal у класса и экземпляра."""
    mock_signal = MagicMock()
    with patch("chutils.qt.signals.require_qt"):
        with patch("chutils.qt.signals.Signal", return_value=mock_signal):
            from chutils.qt.signals import TypedSignal

            class MyWidget:
                data_changed = TypedSignal(str, int)

            # Доступ через класс возвращает сам дескриптор TypedSignal
            assert isinstance(MyWidget.data_changed, TypedSignal)

            # Доступ через экземпляр возвращает BoundTypedSignal
            inst = MyWidget()
            bound = inst.data_changed
            assert bound is not None
