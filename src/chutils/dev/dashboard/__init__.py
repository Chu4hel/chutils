"""
Интерактивный TUI-дашборд для CLI-команд проекта.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from chutils.cli_utils import ConsoleLike


def run_dashboard(console: ConsoleLike) -> None:
    """Запускает TUI-дашборд.

    Args:
        console: Экземпляр консоли для отрисовки.
    """
    from .tui import DashboardTUI
    tui = DashboardTUI(console=console)  # type: ignore[arg-type]
    tui.run()
