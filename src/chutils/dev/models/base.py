from __future__ import annotations

from typing import Any

try:
    from pydantic import BaseModel, Field
except ImportError:
    class BaseModel:  # type: ignore[no-redef]
        """Заглушка Pydantic BaseModel при его отсутствии."""
        pass


    def Field(**kwargs: Any) -> Any:  # type: ignore[no-redef]
        """Заглушка Pydantic Field при его отсутствии.

        Args:
            **kwargs: Произвольные параметры поля.

        Returns:
            None.
        """
        return None


class Breadcrumbs(BaseModel):
    """Метаданные символа (хлебные крошки)."""
    is_async: bool = False
    is_thread_safe: bool = False
    is_heavy: bool = False
    is_abstract: bool = False
    decorators: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    custom_metadata: dict[str, Any] = Field(default_factory=dict)
