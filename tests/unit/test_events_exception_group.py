"""Тесты для класса EventBusExceptionGroup (наследование от ExceptionGroup)."""

from chutils.exceptions import EventBusExceptionGroup


def test_event_bus_exception_group_inheritance():
    """Проверяет, что EventBusExceptionGroup наследуется от ExceptionGroup."""
    eg = EventBusExceptionGroup(
        "test message", [ValueError("error 1"), TypeError("error 2")]
    )
    assert isinstance(eg, ExceptionGroup)


def test_except_star_handling():
    """Проверяет перехват EventBusExceptionGroup с помощью except*."""
    eg = EventBusExceptionGroup("batch errors", [ValueError("err1"), TypeError("err2")])

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
