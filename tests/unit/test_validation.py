from __future__ import annotations

from typing import Any

import pytest


def test_validation_error_inheritance() -> None:
    """Проверяет наследование ChutilsValidationError от ChutilsException."""
    from chutils.exceptions import ChutilsException, ChutilsValidationError
    err = ChutilsValidationError("Test validation error")
    assert isinstance(err, ChutilsException)
    assert isinstance(err, Exception)


def test_validation_error_context_and_properties() -> None:
    """Проверяет сохранение контекста, ошибок и исходной ошибки."""
    from chutils.exceptions import ChutilsValidationError
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
    from chutils.exceptions import ChutilsValidationError
    errors: list[dict[str, Any]] = [
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
    from chutils.exceptions import ChutilsValidationError

    errors: list[dict[str, Any]] = [
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


def test_validate_data_success() -> None:
    """Проверяет успешную валидацию словаря и JSON строки."""
    from pydantic import BaseModel
    from chutils.validation import validate_data

    class User(BaseModel):
        name: str
        age: int

    # Валидация словаря
    res_dict = validate_data(User, {"name": "Alice", "age": 30})
    assert isinstance(res_dict, User)
    assert res_dict.name == "Alice"
    assert res_dict.age == 30

    # Валидация JSON-строки
    res_json = validate_data(User, '{"name": "Bob", "age": 25}')
    assert isinstance(res_json, User)
    assert res_json.name == "Bob"
    assert res_json.age == 25


def test_validate_data_failure() -> None:
    """Проверяет выброс ChutilsValidationError при неверных данных."""
    from pydantic import BaseModel
    from chutils.validation import validate_data
    from chutils.exceptions import ChutilsValidationError

    class User(BaseModel):
        name: str
        age: int

    with pytest.raises(ChutilsValidationError) as exc:
        validate_data(User, {"name": "Alice", "age": "invalid"})

    assert "Ошибка валидации данных" in str(exc.value)
    assert len(exc.value.errors) > 0
    assert exc.value.errors[0]["loc"] == ("age",)
    assert exc.value.raw_error is not None


def test_validate_call_success() -> None:
    """Проверяет успешную работу декоратора @validate_call при правильных аргументах."""
    from chutils.validation import validate_call

    @validate_call
    def greet(name: str, repeat: int = 1) -> str:
        return f"Hello, {name}!" * repeat

    assert greet("Alice", repeat=2) == "Hello, Alice!Hello, Alice!"


def test_validate_call_failure() -> None:
    """Проверяет выброс ChutilsValidationError декоратором @validate_call при неверных типах аргументов."""
    from chutils.validation import validate_call
    from chutils.exceptions import ChutilsValidationError

    @validate_call
    def greet(name: str, repeat: int = 1) -> str:
        return f"Hello, {name}!" * repeat

    with pytest.raises(ChutilsValidationError) as exc:
        greet(123, repeat="two")  # type: ignore[arg-type]

    assert "Ошибка валидации аргументов" in str(exc.value)
    assert len(exc.value.errors) > 0


def test_validate_call_without_pydantic(mocker: Any) -> None:
    """Проверяет выброс OptionalDependencyError при отсутствии Pydantic."""
    from chutils.exceptions import OptionalDependencyError

    # Мокаем доступность pydantic
    mocker.patch("chutils.validation.PYDANTIC_AVAILABLE", False)

    from chutils.validation import validate_call, validate_data
    from pydantic import BaseModel

    class Dummy(BaseModel):
        pass

    # validate_call должен выбрасывать OptionalDependencyError
    @validate_call
    def dummy_func(x: int) -> None:
        pass

    with pytest.raises(OptionalDependencyError) as exc:
        dummy_func(10)
    assert "pydantic" in str(exc.value.context.get("dependency"))

    # validate_data должен также выбрасывать OptionalDependencyError
    with pytest.raises(OptionalDependencyError) as exc:
        validate_data(Dummy, {})
    assert "pydantic" in str(exc.value.context.get("dependency"))


def test_validate_data_invalid_json() -> None:
    """Проверяет выброс ChutilsValidationError при невалидном JSON."""
    from pydantic import BaseModel
    from chutils.validation import validate_data
    from chutils.exceptions import ChutilsValidationError

    class User(BaseModel):
        name: str

    with pytest.raises(ChutilsValidationError) as exc:
        validate_data(User, "{invalid_json")
    assert "невалидный формат JSON" in str(exc.value)


@pytest.mark.asyncio
async def test_validate_call_async_success() -> None:
    """Проверяет асинхронную валидацию при успешном вызове."""
    import asyncio
    from chutils.validation import validate_call

    @validate_call
    async def async_greet(name: str) -> str:
        await asyncio.sleep(0.001)
        return f"Hello, {name}!"

    res = await async_greet("Alice")
    assert res == "Hello, Alice!"


@pytest.mark.asyncio
async def test_validate_call_async_failure() -> None:
    """Проверяет асинхронную валидацию при неверных аргументах."""
    import asyncio
    from chutils.validation import validate_call
    from chutils.exceptions import ChutilsValidationError

    @validate_call
    async def async_greet(name: str) -> str:
        await asyncio.sleep(0.001)
        return f"Hello, {name}!"

    with pytest.raises(ChutilsValidationError) as exc:
        await async_greet(123)  # type: ignore[arg-type]
    assert "Ошибка валидации аргументов при вызове функции" in str(exc.value)


def test_validation_root_imports() -> None:
    """Проверяет возможность импорта функций и исключений напрямую из chutils."""
    import chutils

    assert hasattr(chutils, "validate_data")
    assert hasattr(chutils, "validate_call")
    assert hasattr(chutils, "ChutilsValidationError")


def test_validation_lazy_loading_no_pydantic() -> None:
    """Проверяет, что при отсутствии Pydantic импорт из корня не вызывает каскадных ошибок."""
    import sys

    # Временно прячем pydantic из sys.modules
    orig_pydantic = sys.modules.get("pydantic")
    sys.modules["pydantic"] = None  # type: ignore[assignment]

    try:
        import chutils.validation
        assert chutils.validation is not None
    finally:
        if orig_pydantic is not None:
            sys.modules["pydantic"] = orig_pydantic
        else:
            sys.modules.pop("pydantic", None)
