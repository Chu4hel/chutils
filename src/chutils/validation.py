from __future__ import annotations

import functools
import inspect
import json
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, ParamSpec, TypeVar, cast

from chutils.env import PYDANTIC_AVAILABLE

if TYPE_CHECKING:
    from pydantic import BaseModel

P = ParamSpec("P")
R = TypeVar("R")
T = TypeVar("T", bound="BaseModel")


def validate_data(model: type[T], data: dict[str, Any] | str) -> T:
    """Валидирует словарь или JSON-строку по заданной Pydantic модели.

    Args:
        model: Класс Pydantic модели для валидации.
        data: Данные для валидации в виде словаря или JSON-строки.

    Returns:
        Экземпляр провалидированной модели Pydantic.

    Raises:
        OptionalDependencyError: Если пакет pydantic не установлен.
        ChutilsValidationError: Если данные не прошли валидацию или JSON невалиден.
    """
    if not PYDANTIC_AVAILABLE:
        from chutils.exceptions import OptionalDependencyError

        raise OptionalDependencyError(
            "Pydantic не установлен.",
            dependency="pydantic",
            hint="Установите его: pip install chutils[pydantic]",
        )

    import pydantic

    parsed_data: dict[str, Any]
    if isinstance(data, str):
        try:
            parsed_data = json.loads(data)
        except json.JSONDecodeError as e:
            from chutils.exceptions import ChutilsValidationError

            raise ChutilsValidationError(
                "Ошибка валидации данных: невалидный формат JSON",
                errors=[{"loc": (), "msg": f"JSONDecodeError: {e}", "type": "json_decode_error"}],
                raw_error=e,
                hint="Проверьте корректность формата JSON строки.",
            ) from e
    else:
        parsed_data = data

    try:
        return model.model_validate(parsed_data)
    except pydantic.ValidationError as e:
        from chutils.exceptions import ChutilsValidationError

        raise ChutilsValidationError(
            "Ошибка валидации данных по Pydantic модели",
            errors=cast(list[dict[str, Any]], e.errors()),
            raw_error=e,
            hint="Проверьте соответствие типов и структуры передаваемых данных.",
        ) from e


def validate_call(func: Callable[P, R]) -> Callable[P, R]:
    """Декоратор для автоматической валидации аргументов вызова функции.

    Использует pydantic.validate_call под капотом, если pydantic установлен.
    В случае ошибки валидации выбрасывает ChutilsValidationError.

    Args:
        func: Декорируемая функция (синхронная или асинхронная).

    Returns:
        Декорированная функция с автоматической валидацией аргументов.

    Raises:
        OptionalDependencyError: Если пакет pydantic не установлен в системе.
    """
    if not PYDANTIC_AVAILABLE:
        @functools.wraps(func)
        def fallback_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            from chutils.exceptions import OptionalDependencyError

            raise OptionalDependencyError(
                "Pydantic не установлен.",
                dependency="pydantic",
                hint="Установите его: pip install chutils[pydantic]",
            )

        return fallback_wrapper

    import pydantic

    validated_func = pydantic.validate_call(func)

    if inspect.iscoroutinefunction(func):

        @functools.wraps(func)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> Any:
            try:
                return await cast(Any, validated_func(*args, **kwargs))
            except pydantic.ValidationError as e:
                from chutils.exceptions import ChutilsValidationError

                raise ChutilsValidationError(
                    f"Ошибка валидации аргументов при вызове функции '{func.__name__}'",
                    errors=cast(list[dict[str, Any]], e.errors()),
                    raw_error=e,
                    hint="Убедитесь, что типы переданных параметров соответствуют сигнатуре функции.",
                ) from e

        return async_wrapper  # type: ignore[return-value]
    else:

        @functools.wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            try:
                return validated_func(*args, **kwargs)
            except pydantic.ValidationError as e:
                from chutils.exceptions import ChutilsValidationError

                raise ChutilsValidationError(
                    f"Ошибка валидации аргументов при вызове функции '{func.__name__}'",
                    errors=cast(list[dict[str, Any]], e.errors()),
                    raw_error=e,
                    hint="Убедитесь, что типы переданных параметров соответствуют сигнатуре функции.",
                ) from e

        return sync_wrapper
