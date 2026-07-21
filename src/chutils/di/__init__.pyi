from collections.abc import Callable
from typing import Any, TypeVar

T = TypeVar("T")


class Container:
    def __init__(self) -> None: ...

    def register(
            self,
            dependency_type: type[Any] | str,
            provider: Callable[..., Any] | None = None,
            scope: str = "singleton",
    ) -> None: ...

    def has_provider(self, dependency_type: type[Any] | str) -> bool: ...

    def resolve(self, dependency_type: type[T] | str | Any) -> T: ...

    def clear(self) -> None: ...


default_container: Container


def provide(
        scope: str = "singleton", container: Container | None = None
) -> Callable[[Any], Any]: ...


def inject(
        func_or_container: Callable[..., Any] | Container | None = None,
        *,
        container: Container | None = None,
) -> Any: ...


def Inject() -> Any: ...
