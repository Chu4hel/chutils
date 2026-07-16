from __future__ import annotations

from typing import Any

from .base import BaseModel, Field
from .node import Node


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
    metadata: dict[str, Any] = Field(default_factory=dict)
