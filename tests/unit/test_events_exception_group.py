"""Тесты для класса EventBusExceptionGroup (наследование от ExceptionGroup)."""
import sys

from chutils.exceptions import EventBusExceptionGroup


def test_event_bus_exception_group_inheritance():
    """Проверяет, что EventBusExceptionGroup наследуется от ExceptionGroup."""
    if sys.version_info >= (3, 11):
        expected_base = ExceptionGroup
    else:
        from exceptiongroup import ExceptionGroup as expected_base

    eg = EventBusExceptionGroup("test message", [ValueError("error 1"), TypeError("error 2")])
    assert isinstance(eg, expected_base)


def test_except_star_handling():
    """Проверяет перехват EventBusExceptionGroup с помощью except* на Python >= 3.11 или ExceptionGroup на 3.10."""
    eg = EventBusExceptionGroup("batch errors", [ValueError("err1"), TypeError("err2")])

    if sys.version_info >= (3, 11):
        locs = {"eg": eg, "value_error_caught": False, "type_error_caught": False}
        code = """
try:
    raise eg
except* ValueError:
    value_error_caught = True
except* TypeError:
    type_error_caught = True
"""
        exec(code, {}, locs)
        assert locs["value_error_caught"] is True
        assert locs["type_error_caught"] is True
    else:
        from exceptiongroup import ExceptionGroup as EG
        try:
            raise eg
        except EG as e:
            assert len(e.exceptions) == 2
            assert isinstance(e.exceptions[0], ValueError)
            assert isinstance(e.exceptions[1], TypeError)
