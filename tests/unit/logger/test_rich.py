import logging
from unittest.mock import MagicMock

import pytest
from chutils.env import is_rich_enabled
from chutils.logger import setup_logger


@pytest.fixture
def mock_rich(monkeypatch, mocker):
    """
    Мокаем наличие Rich.
    """
    mock_handler_instance = MagicMock(spec=logging.Handler)
    # Патчим RICH_AVAILABLE в модуле env
    monkeypatch.setattr("chutils.env.RICH_AVAILABLE", True)
    # Патчим сам класс RichHandler в источнике (библиотеке rich),
    # чтобы локальные импорты внутри функций setup_logger тоже получали мок.
    mocker.patch("rich.logging.RichHandler", return_value=mock_handler_instance, create=True)
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
