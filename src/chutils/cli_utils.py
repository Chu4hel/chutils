import os
import re
import shutil
import sys
from typing import Any, Optional

from .env import RICH_AVAILABLE, is_rich_enabled

if RICH_AVAILABLE:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel


class FallbackConsole:
    """
    Упрощенный аналог rich.Console для случаев, когда rich не установлен.
    """

    def __init__(self, stderr: bool = False):
        self._is_stderr = stderr

    @property
    def file(self):
        return sys.stderr if self._is_stderr else sys.stdout

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
_console_width: Optional[int] = None


def set_console_width(width: int):
    """
    Устанавливает ширину консоли и сбрасывает кэшированные экземпляры консолей.
    """
    global _console_width, _console, _err_console
    _console_width = width
    _console = None
    _err_console = None


def _get_default_width() -> Optional[int]:
    """Определяет ширину консоли по умолчанию с учетом IDE."""
    if _console_width is not None:
        return _console_width

    # Пытаемся определить размер терминала
    width, _ = shutil.get_terminal_size(fallback=(80, 24))

    # Специфичное поведение для PyCharm (часто ограничивает ширину в 80 символов при запуске логов)
    if os.getenv("PYCHARM_HOSTED") == "1" and width == 80:
        return 140

    return width


def get_console(stderr: bool = False) -> Any:
    """
    Возвращает экземпляр rich.Console или FallbackConsole.
    """
    global _console, _err_console

    if stderr:
        if _err_console is not None:
            return _err_console
        if is_rich_enabled():
            _err_console = Console(stderr=True, width=_get_default_width())
        else:
            _err_console = FallbackConsole(stderr=True)
        return _err_console

    if _console is not None:
        return _console

    if is_rich_enabled():
        _console = Console(width=_get_default_width())
    else:
        _console = FallbackConsole()
    return _console
