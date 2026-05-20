import os
from typing import Any

# Пытаемся импортировать rich
RICH_AVAILABLE = False
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel

    RICH_AVAILABLE = True
except ImportError:
    pass


def is_color_enabled() -> bool:
    """Проверяет, включена ли цветовая индикация."""
    no_color = os.getenv("NO_COLOR", "").lower() in ["true", "1", "yes", "y"]
    ch_no_color = os.getenv("CH_NO_COLOR", "").lower() in ["true", "1", "yes", "y"]
    return not (no_color or ch_no_color)


class FallbackConsole:
    """
    Упрощенный аналог rich.Console для случаев, когда rich не установлен.
    """

    def print(self, *args, **kwargs):
        # Игнорируем специфичные для Rich аргументы
        kwargs.pop("style", None)
        kwargs.pop("justify", None)
        kwargs.pop("markup", None)
        kwargs.pop("highlight", None)

        # Если аргумент один и это не строка (например, Table или Panel),
        # пытаемся вывести его как-то осмысленно или просто repr.
        if len(args) == 1 and not isinstance(args[0], str):
            obj = args[0]
            if hasattr(obj, "title") and obj.title:
                print(f"=== {obj.title} ===")
            # Для таблиц и прочего без rich просто выводим repr или ничего
            return

        print(*args, **kwargs)

    def rule(self, title=""):
        print(f"\n--- {title} ---\n")


_console = None


def get_console() -> Any:
    """
    Возвращает экземпляр rich.Console или FallbackConsole.
    """
    global _console
    if _console is not None:
        return _console

    if RICH_AVAILABLE and is_color_enabled():
        _console = Console()
    else:
        _console = FallbackConsole()
    return _console
