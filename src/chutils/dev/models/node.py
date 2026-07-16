from __future__ import annotations

from .base import BaseModel, Field
from .symbol import Symbol


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
