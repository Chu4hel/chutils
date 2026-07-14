from __future__ import annotations

from chutils.exceptions import ChutilsException, ChutilsValidationError


def test_validation_error_inheritance() -> None:
    """Проверяет наследование ChutilsValidationError от ChutilsException."""
    err = ChutilsValidationError("Test validation error")
    assert isinstance(err, ChutilsException)
    assert isinstance(err, Exception)


def test_validation_error_context_and_properties() -> None:
    """Проверяет сохранение контекста, ошибок и исходной ошибки."""
    raw = ValueError("Raw error")
    errors = [{"loc": ("field",), "msg": "Missing field", "type": "value_error"}]

    err = ChutilsValidationError(
        message="Invalid data",
        errors=errors,
        raw_error=raw,
        hint="Fix field",
        extra_info="some_context"
    )

    assert err.message == "Invalid data"
    assert err.errors == errors
    assert err.raw_error is raw
    assert err.hint == "Fix field"
    assert err.context == {"extra_info": "some_context"}


def test_validation_error_str_formatting() -> None:
    """Проверяет plain-text форматирование списка ошибок в __str__."""
    errors = [
        {"loc": ("user", "name"), "msg": "Field required", "type": "missing", "input": None},
        {"loc": ("user", "age"), "msg": "Input should be a valid integer", "type": "int_parsing", "input": "twenty"}
    ]

    err = ChutilsValidationError("Validation failed", errors=errors)
    err_str = str(err)

    assert "Validation failed" in err_str
    assert "user.name" in err_str
    assert "Field required" in err_str
    assert "user.age" in err_str
    assert "Input should be a valid integer" in err_str
    assert "twenty" in err_str


def test_validation_error_rich_formatting() -> None:
    """Проверяет форматирование в rich-таблицу при наличии rich."""
    from rich.table import Table

    errors = [
        {"loc": ("user", "name"), "msg": "Field required", "type": "missing", "input": None},
        {"loc": ("user", "age"), "msg": "Input should be a valid integer", "type": "int_parsing", "input": "twenty"}
    ]

    err = ChutilsValidationError("Validation failed", errors=errors)

    # Вызываем метод __rich__
    table = err.__rich__()
    assert isinstance(table, Table)
    assert table.title == "Validation failed"
    # Проверяем колонки
    assert [col.header for col in table.columns] == ["Поле / Путь", "Причина ошибки", "Полученное значение"]
