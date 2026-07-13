"""
Инструменты разработчика для анализа кодовой базы и генерации контекста.
"""
from __future__ import annotations

from .ai_lint import Rule as Rule, LintResult as LintResult, LinterEngine as LinterEngine
from .chat_context import collect_context_slice as collect_context_slice, run_interactive_menu as run_interactive_menu
from .generate_few_shot import generate_few_shot_bank as generate_few_shot_bank
from .mock_server import MockServerRunner as MockServerRunner
from .scaffold import Scaffolder as Scaffolder

__all__ = [
    "Rule",
    "LintResult",
    "LinterEngine",
    "collect_context_slice",
    "generate_few_shot_bank",
    "run_interactive_menu",
    "MockServerRunner",
    "Scaffolder",
]
