"""
Модуль для кроссплатформенного неблокирующего чтения ввода с клавиатуры.
"""
from __future__ import annotations

import sys


class RawTerminalUnix:
    """Контекстный менеджер для перевода Unix терминала в raw режим."""

    def __init__(self) -> None:
        """Инициализирует контекстный менеджер."""
        import termios
        self.fd = sys.stdin.fileno()
        self.old_settings = termios.tcgetattr(self.fd)  # type: ignore[attr-defined]

    def __enter__(self) -> RawTerminalUnix:
        """Включает raw режим для терминала."""
        import tty
        tty.setraw(self.fd)  # type: ignore[attr-defined]
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        """Восстанавливает исходные настройки терминала."""
        import termios
        termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old_settings)  # type: ignore[attr-defined]


class InputReader:
    """Кроссплатформенный класс для неблокирующего чтения ввода."""

    def __init__(self) -> None:
        """Инициализирует InputReader."""
        self.is_win = (sys.platform == "win32")
        self.raw_term: RawTerminalUnix | None = None

    def __enter__(self) -> InputReader:
        """Входит в контекст, подготавливая терминал (для Unix)."""
        if not self.is_win:
            self.raw_term = RawTerminalUnix()
            self.raw_term.__enter__()
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        """Выходит из контекста, восстанавливая терминал (для Unix)."""
        if self.raw_term is not None:
            self.raw_term.__exit__(exc_type, exc_val, exc_tb)
            self.raw_term = None

    def get_key(self) -> str | None:
        """Читает одно нажатие клавиши без блокировки.

        Returns:
            Строка с кодом нажатой клавиши или None, если ничего не нажато.
        """
        # Динамически перевычисляем is_win на случай смены платформы в тестах
        self.is_win = (sys.platform == "win32")

        if self.is_win:
            return self._get_key_win()
        else:
            return self._get_key_unix()

    def _get_key_win(self) -> str | None:
        """Читает клавишу на Windows."""
        import msvcrt
        if msvcrt.kbhit():
            ch = msvcrt.getch()
            # Ctrl+C
            if ch == b"\x03":
                return "ctrl-c"

            # Спецсимволы (стрелки, Shift+Tab и др.)
            if ch in (b"\x00", b"\xe0"):
                ch2 = msvcrt.getch()
                code = ch2.hex()
                win_special = {
                    "48": "up",
                    "50": "down",
                    "4b": "left",
                    "4d": "right",
                    "0f": "shift-tab",
                }
                return win_special.get(code, f"special-{code}")

            if ch in (b"\r", b"\n"):
                return "enter"
            if ch == b"\x1b":
                return "escape"
            if ch == b"\x08":
                return "backspace"
            if ch == b"\t":
                return "tab"

            try:
                return ch.decode("utf-8")
            except Exception:
                return None
        return None

    def _get_key_unix(self) -> str | None:
        """Читает клавишу на Unix."""
        import select
        rlist, _, _ = select.select([sys.stdin], [], [], 0.0)
        if rlist:
            ch = sys.stdin.read(1)
            # Ctrl+C
            if ch == "\x03":
                return "ctrl-c"

            # Спецсимволы
            if ch == "\x1b":
                rlist_spec, _, _ = select.select([sys.stdin], [], [], 0.05)
                if rlist_spec:
                    ch2 = sys.stdin.read(1)
                    if ch2 == "[":
                        ch3 = sys.stdin.read(1)
                        if ch3 == "A":
                            return "up"
                        elif ch3 == "B":
                            return "down"
                        elif ch3 == "C":
                            return "right"
                        elif ch3 == "D":
                            return "left"
                        elif ch3 == "Z":
                            return "shift-tab"
                    return "escape"
                return "escape"

            if ch in ("\n", "\r"):
                return "enter"
            if ch == "\t":
                return "tab"
            if ch in ("\x7f", "\x08"):
                return "backspace"

            return ch
        return None
