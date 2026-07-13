from __future__ import annotations

import os
import re
import shutil
import sys
import typing as t
from typing import Any, Union

from .env import RICH_AVAILABLE, is_rich_enabled

if t.TYPE_CHECKING:
    from rich.console import Console as _RichConsole

    ConsoleLike = Union[_RichConsole, "FallbackConsole"]
else:
    ConsoleLike = Any

if RICH_AVAILABLE:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
else:
    Console = None  # type: ignore[assignment, misc]
    Table = None  # type: ignore[assignment, misc]
    Panel = None  # type: ignore[assignment, misc]


class FallbackConsole:
    """
    Упрощенный аналог rich.Console для случаев, когда rich не установлен.
    """

    def __init__(self, stderr: bool = False):
        self._is_stderr = stderr

    @property
    def width(self) -> int:
        """Возвращает текущую установленную ширину консоли."""
        return _get_default_width() or 80

    @property
    def file(self) -> t.TextIO:
        return sys.stderr if self._is_stderr else sys.stdout

    @staticmethod
    def _strip_markup(text: str) -> str:
        """Удаляет теги rich, стараясь не трогать обычные квадратные скобки."""
        # Регулярное выражение для поиска тегов rich: [style], [/style], [color], [#hex]
        # Мы ищем слова, которые часто используются в стилях Rich, или коды цветов.
        return re.sub(
            r"\[/?(?:bold|italic|underline|strike|dim|reverse|blink|red|green|yellow|blue|magenta|cyan|white|black|grey|#[\da-fA-F]{3,6}|rgb\(\d+,\d+,\d+\)|on\s+\w+)[^\]]*\]",
            "", text)

    def print(self, *args: Any, **kwargs: Any) -> None:
        # Игнорируем специфичные для Rich аргументы
        kwargs.pop("style", None)
        kwargs.pop("justify", None)
        markup = kwargs.pop("markup", True)
        kwargs.pop("highlight", None)

        # Устанавливаем файл для вывода, если он не задан явно.
        # Берем sys.stdout/stderr прямо сейчас, чтобы подхватить подмену в тестах.
        if "file" not in kwargs:
            kwargs["file"] = sys.stderr if self._is_stderr else sys.stdout

        processed_args: list[Any] = []
        for arg in args:
            if isinstance(arg, str) and markup:
                processed_args.append(self._strip_markup(arg))
            else:
                # Если аргумент не строка (например, Table или Panel),
                # пытаемся вывести его как-то осмысленно или просто repr.
                if not isinstance(arg, str):
                    is_panel = type(arg).__name__ == "Panel"
                    if hasattr(arg, "title") and getattr(arg, "title"):
                        processed_args.append(f"=== {self._strip_markup(str(getattr(arg, 'title')))} ===")
                        if not is_panel:
                            continue

                    if is_panel:
                        renderable = getattr(arg, "renderable", "")
                        processed_args.append(self._strip_markup(str(renderable)))
                        continue

                processed_args.append(arg)

        print(*processed_args, **kwargs)

    def rule(self, title: str = "") -> None:
        f = sys.stderr if self._is_stderr else sys.stdout
        print(f"\n--- {title} ---\n", file=f)


_console: ConsoleLike | None = None
_err_console: ConsoleLike | None = None
_console_width: int | None = None


def set_console_width(width: int) -> None:
    """
    Устанавливает ширину консоли и сбрасывает кэшированные экземпляры консолей.
    """
    global _console_width, _console, _err_console
    _console_width = width
    _console = None
    _err_console = None


def _get_default_width() -> int | None:
    """Определяет ширину консоли по умолчанию с учетом IDE."""
    if _console_width is not None:
        return _console_width

    # Пытаемся определить размер терминала
    width, _ = shutil.get_terminal_size(fallback=(80, 24))

    # Специфичное поведение для PyCharm (часто ограничивает ширину в 80 символов при запуске логов)
    if os.getenv("PYCHARM_HOSTED") == "1" and width == 80:
        return 140

    return width


def get_console(stderr: bool = False) -> ConsoleLike:
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
