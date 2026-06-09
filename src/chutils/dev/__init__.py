"""
Инструменты разработчика для анализа кодовой базы и генерации контекста.
"""
from __future__ import annotations

from .ai_lint import Rule as Rule, LintResult as LintResult, LinterEngine as LinterEngine

__all__ = [
    "Rule",
    "LintResult",
    "LinterEngine"
]
