import os
from unittest.mock import patch

from chutils.cli_utils import get_console, set_console_width, _get_default_width


def test_manual_console_width():
    """Проверка ручной установки ширины консоли."""
    set_console_width(120)
    assert _get_default_width() == 120

    console = get_console()
    assert console.width == 120

    set_console_width(200)
    assert _get_default_width() == 200
    console = get_console()
    assert console.width == 200

    # Сброс для других тестов
    set_console_width(None)


def test_autodetect_standard():
    """Проверка стандартного автоопределения."""
    set_console_width(None)
    with patch("shutil.get_terminal_size") as mock_size:
        mock_size.return_value = os.terminal_size((100, 24))
        with patch.dict(os.environ, {"PYCHARM_HOSTED": "1" if False else "0"}):
            assert _get_default_width() == 100


def test_autodetect_pycharm_default():
    """Проверка автоопределения для PyCharm (когда ширина 80)."""
    set_console_width(None)
    with patch("shutil.get_terminal_size") as mock_size:
        mock_size.return_value = os.terminal_size((80, 24))
        with patch.dict(os.environ, {"PYCHARM_HOSTED": "1"}):
            # Должно расшириться до 140
            assert _get_default_width() == 140


def test_autodetect_pycharm_custom():
    """Проверка автоопределения для PyCharm (когда ширина НЕ 80)."""
    set_console_width(None)
    with patch("shutil.get_terminal_size") as mock_size:
        mock_size.return_value = os.terminal_size((160, 24))
        with patch.dict(os.environ, {"PYCHARM_HOSTED": "1"}):
            # Должно оставить как есть
            assert _get_default_width() == 160
