from typing import Any, Callable, ParamSpec, TypeVar

from pydantic import BaseModel

P = ParamSpec("P")
R = TypeVar("R")
T = TypeVar("T", bound=BaseModel)


def validate_data(model: type[T], data: dict[str, Any] | str) -> T: ...


def validate_call(func: Callable[P, R]) -> Callable[P, R]: ...
