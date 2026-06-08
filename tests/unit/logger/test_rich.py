import logging
import sys
from unittest.mock import MagicMock

import pytest

from chutils.env import is_rich_enabled
from chutils.logger import setup_logger


@pytest.fixture
def mock_rich(monkeypatch):
    """
    Мокаем наличие Rich, даже если библиотека не установлена.
    """
    mock_handler_instance = MagicMock(spec=logging.Handler)
    mock_rich_logging = MagicMock()
    mock_rich_logging.RichHandler.return_value = mock_handler_instance

    mock_console_class = MagicMock()
    mock_console_instance = MagicMock()
    mock_console_class.return_value = mock_console_instance

    # Имитируем наличие модулей в системе для всех импортов
    monkeypatch.setitem(sys.modules, "rich", MagicMock())
    monkeypatch.setitem(sys.modules, "rich.logging", mock_rich_logging)
    monkeypatch.setitem(sys.modules, "rich.console", MagicMock(Console=mock_console_class))
    monkeypatch.setitem(sys.modules, "rich.table", MagicMock(Table=MagicMock()))
    monkeypatch.setitem(sys.modules, "rich.panel", MagicMock(Panel=MagicMock()))

    # Патчим RICH_AVAILABLE в модуле env
    monkeypatch.setattr("chutils.env.RICH_AVAILABLE", True)

    # Инъектируем в cli_utils, так как он мог быть уже импортирован с RICH_AVAILABLE=False
    import chutils.cli_utils
    monkeypatch.setattr(chutils.cli_utils, "Console", mock_console_class)
    monkeypatch.setattr(chutils.cli_utils, "Table", MagicMock())
    monkeypatch.setattr(chutils.cli_utils, "Panel", MagicMock())

    return mock_handler_instance


def test_rich_handler_used_when_available(mock_rich, monkeypatch, reset_chutils_state):
    """
    Проверяет, что RichHandler используется, когда библиотека доступна и цвета не отключены.
    """
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.delenv("CH_NO_COLOR", raising=False)

    logger = setup_logger("test_rich_logger", force_reconfigure=True)

    # Проверяем, что среди обработчиков есть наш мок (RichHandler)
    assert any(h == mock_rich for h in logger.handlers)


def test_rich_handler_not_used_when_no_color(mock_rich, monkeypatch, reset_chutils_state):
    """
    Проверяет, что RichHandler НЕ используется при NO_COLOR=1.
    """
    monkeypatch.setenv("NO_COLOR", "1")

    logger = setup_logger("test_rich_no_color", force_reconfigure=True)

    # Проверяем, что RichHandler НЕ используется
    assert not any(h == mock_rich for h in logger.handlers)
    # Должен быть обычный StreamHandler
    assert any(isinstance(h, logging.StreamHandler) and not isinstance(h, MagicMock) for h in logger.handlers)


def test_rich_handler_not_used_when_rich_unavailable(monkeypatch, reset_chutils_state):
    """
    Проверяет, что при отсутствии rich используется стандартный StreamHandler.
    """
    monkeypatch.setattr("chutils.env.RICH_AVAILABLE",
                        False)

    logger = setup_logger("test_no_rich", force_reconfigure=True)

    # Не должен упасть и должен использовать StreamHandler
    assert any(isinstance(h, logging.StreamHandler) for h in logger.handlers)


def test_is_rich_enabled_logic(monkeypatch):
    """
    Проверяет логику функции is_rich_enabled.
    """
    monkeypatch.setattr("chutils.env.RICH_AVAILABLE",
                        True)

    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.delenv("CH_NO_COLOR", raising=False)
    assert is_rich_enabled() is True

    monkeypatch.setenv("NO_COLOR", "true")
    assert is_rich_enabled() is False

    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("CH_NO_COLOR", "1")
    assert is_rich_enabled() is False
