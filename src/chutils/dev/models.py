"""
Модели данных для иерархического семантического индекса.
"""

from typing import Dict, List, Optional, Any

from pydantic import BaseModel, Field


class Breadcrumbs(BaseModel):
    """Метаданные символа (хлебные крошки)."""
    is_async: bool = False
    is_thread_safe: bool = False
    is_heavy: bool = False
    decorators: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    custom_metadata: Dict[str, Any] = Field(default_factory=dict)


class Symbol(BaseModel):
    """Описание функции, класса или константы."""
    name: str
    type: str  # function, class, constant, method
    signature: Optional[str] = None
    summary: str = ""
    docstring: Optional[str] = None
    breadcrumbs: Breadcrumbs = Field(default_factory=Breadcrumbs)
    line_number: int = 0


class Node(BaseModel):
    """Узел дерева (пакет или модуль)."""
    name: str
    path: str  # Относительный путь от корня проекта
    type: str  # package, module
    layer: str = "internal"  # public, private, internal, infrastructure
    summary: str = ""
    docstring: Optional[str] = None
    children: List["Node"] = Field(default_factory=list)
    symbols: List[Symbol] = Field(default_factory=list)


class GraphEdge(BaseModel):
    """Связь в графе зависимостей."""
    source: str  # Путь к исходному модулю
    target: str  # Путь к целевому модулю
    weight: int = 1  # Количество импортов/вызовов


class ProjectIndex(BaseModel):
    """Корневой объект семантического индекса."""
    version: str = "1.0"
    project_name: str = "chutils"
    root: Node
    dependency_graph: List[GraphEdge] = Field(default_factory=list)
