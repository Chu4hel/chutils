from collections.abc import Callable
from typing import Any, ParamSpec, TypeVar

from pydantic import BaseModel

_P = ParamSpec("_P")
_R = TypeVar("_R")
_T = TypeVar("_T", bound=BaseModel)

def validate_data(model: type[_T], data: dict[str, Any] | str) -> _T: ...
def validate_call(func: Callable[_P, _R]) -> Callable[_P, _R]: ...
