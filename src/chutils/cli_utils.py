import os
import re
import sys
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

    def __init__(self, stderr: bool = False):
        self._is_stderr = stderr

    def _strip_markup(self, text: str) -> str:
        """Удаляет простейшие теги rich типа [bold]."""
        return re.sub(r"\[/?[\w\s,=#]*\]", "", text)

    def print(self, *args, **kwargs):
        # Игнорируем специфичные для Rich аргументы
        kwargs.pop("style", None)
        kwargs.pop("justify", None)
        markup = kwargs.pop("markup", True)
        kwargs.pop("highlight", None)

        # Устанавливаем файл для вывода, если он не задан явно.
        # Берем sys.stdout/stderr прямо сейчас, чтобы подхватить подмену в тестах.
        if "file" not in kwargs:
            kwargs["file"] = sys.stderr if self._is_stderr else sys.stdout

        processed_args = []
        for arg in args:
            if isinstance(arg, str) and markup:
                processed_args.append(self._strip_markup(arg))
            else:
                # Если аргумент не строка (например, Table или Panel),
                # пытаемся вывести его как-то осмысленно или просто repr.
                if not isinstance(arg, str):
                    if hasattr(arg, "title") and arg.title:
                        processed_args.append(f"=== {arg.title} ===")
                        continue
                processed_args.append(arg)

        print(*processed_args, **kwargs)

    def rule(self, title=""):
        f = sys.stderr if self._is_stderr else sys.stdout
        print(f"\n--- {title} ---\n", file=f)


_console = None
_err_console = None


def get_console(stderr: bool = False) -> Any:
    """
    Возвращает экземпляр rich.Console или FallbackConsole.
    """
    global _console, _err_console

    if stderr:
        if _err_console is not None:
            return _err_console
        if RICH_AVAILABLE and is_color_enabled():
            _err_console = Console(stderr=True)
        else:
            _err_console = FallbackConsole(stderr=True)
        return _err_console

    if _console is not None:
        return _console

    if RICH_AVAILABLE and is_color_enabled():
        _console = Console()
    else:
        _console = FallbackConsole()
    return _console
