from __future__ import annotations

from .base import BaseModel, Field, Breadcrumbs


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
