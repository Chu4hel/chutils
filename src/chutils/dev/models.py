"""
Модели данных для иерархического семантического индекса.
"""
from __future__ import annotations

from typing import Any

try:
    from pydantic import BaseModel, Field
except ImportError:
    # Заглушки для обеспечения возможности импорта модуля без pydantic
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


class Symbol(BaseModel):
    """Описание функции, класса или константы."""
    name: str
    type: str
    """function, class, constant, method"""
    layer: str = "internal"
    """public, private, internal, infrastructure"""
    signature: str | None = None
    summary: str = ""
    docstring: str | None = None
    breadcrumbs: Breadcrumbs = Field(default_factory=Breadcrumbs)
    line_number: int = 0
    bases: list[str] = Field(default_factory=list)
    """Базовые классы (для классов)"""
    children: list[Symbol] = Field(default_factory=list)
    """Вложенные символы (например, методы класса)"""


class Node(BaseModel):
    """Узел дерева (пакет или модуль)."""
    name: str
    path: str
    """Относительный путь от корня проекта"""
    type: str
    """package, module"""
    layer: str = "internal"
    """public, private, internal, infrastructure"""
    summary: str = ""
    docstring: str | None = None
    children: list[Node] = Field(default_factory=list)
    symbols: list[Symbol] = Field(default_factory=list)


class GraphEdge(BaseModel):
    """Связь в графе зависимостей."""
    source: str
    """Путь к исходному модулю"""
    target: str
    """Путь к целевому модулю"""
    weight: int = 1
    """Количество импортов/вызовов"""


class ProjectExample(BaseModel):
    """Описание few-shot примера (кейса)."""
    name: str
    description: str
    good_pattern: str
    bad_pattern: str


class ProjectIndex(BaseModel):
    """Корневой объект семантического индекса."""
    version: str = "1.0"
    project_name: str = "chutils"
    root: Node
    dependency_graph: list[GraphEdge] = Field(default_factory=list)
    examples: list[ProjectExample] = Field(default_factory=list)
