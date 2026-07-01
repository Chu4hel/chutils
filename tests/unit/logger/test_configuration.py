import logging
from unittest.mock import patch

import pytest

from chutils.logger import setup_logger, LogLevel


def test_args_have_highest_priority(project_with_marker, reset_chutils_state):
    """Тест: Аргументы, переданные в функцию, имеют наивысший приоритет."""
    fs, project_root = project_with_marker

    # Конфигурационный файл с одними значениями
    config_content = """
Logging:
  log_level: WARNING
  rotation_type: size
  compress: true
"""
    fs.create_file(project_root / "config.yml", contents=config_content)

    # В функцию передаем другие значения
    with patch('chutils.logger.internal.builder.SafeTimedRotatingFileHandler') as mock_safe_handler, \
            patch('chutils.logger.internal.builder.CompressingRotatingFileHandler') as mock_compressing_handler:
        logger = setup_logger(
            "test_args_priority",
            log_level=LogLevel.INFO,
            rotation_type='time',
            compress=False,
            force_reconfigure=True
        )

        # Проверяем, что применились значения из аргументов, а не из конфига
        assert logger.level == logging.INFO
        mock_safe_handler.assert_called_once()
        mock_compressing_handler.assert_not_called()


def test_config_overrides_defaults(project_with_marker, reset_chutils_state):
    """Тест: Конфигурационный файл имеет приоритет над значениями по умолчанию."""
    fs, project_root = project_with_marker

    config_content = """
Logging:
  log_level: WARNING
  rotation_type: size
  compress: true
"""
    fs.create_file(project_root / "config.yml", contents=config_content)

    with patch('chutils.logger.internal.builder.SafeTimedRotatingFileHandler') as mock_safe_handler, \
            patch('chutils.logger.internal.builder.CompressingRotatingFileHandler') as mock_compressing_handler:
        logger = setup_logger("test_config_priority", force_reconfigure=True)

        # Проверяем, что применились значения из конфига
        assert logger.level == logging.WARNING
        mock_compressing_handler.assert_called_once()
        mock_safe_handler.assert_not_called()


def test_defaults_are_used_when_no_config(project_with_marker, reset_chutils_state):
    """Тест: Значения по умолчанию используются, если нет ни аргументов, ни конфига."""
    # фикстура project_with_marker создает только pyproject.toml, но не config.yml
    fs, project_root = project_with_marker

    with patch('chutils.logger.internal.builder.SafeTimedRotatingFileHandler') as mock_safe_handler, \
            patch('chutils.logger.internal.builder.CompressingRotatingFileHandler') as mock_compressing_handler:
        logger = setup_logger("test_default_priority", force_reconfigure=True)

        # Проверяем, что применились значения по умолчанию
        assert logger.level == logging.INFO
        mock_safe_handler.assert_called_once()
        mock_compressing_handler.assert_not_called()


def test_kwargs_passthrough(project_with_marker, reset_chutils_state):
    """Тестирует, что произвольные kwargs корректно передаются в конструктор обработчика."""
    fs, project_root = project_with_marker

    with patch('chutils.logger.internal.builder.SafeTimedRotatingFileHandler') as mock_handler:
        setup_logger(
            "test_kwargs",
            force_reconfigure=True,
            delay=True,
            mode='w',
            errors='ignore'
        )

        # Проверяем, что конструктор был вызван с нашими kwargs
        mock_handler.assert_called_once()
        call_kwargs = mock_handler.call_args.kwargs
        assert call_kwargs.get('delay') is True
        assert call_kwargs.get('mode') == 'w'
        assert call_kwargs.get('errors') == 'ignore'


def test_setup_logger_invalid_kwargs(reset_chutils_state):
    """Проверяет, что setup_logger выбрасывает TypeError при передаче невалидных параметров."""
    with pytest.raises(TypeError, match="setup_logger\\(\\) got an unexpected keyword argument 'level'"):
        setup_logger("test_invalid_kwargs", level="DEBUG")

    with pytest.raises(TypeError, match="setup_logger\\(\\) got an unexpected keyword argument 'unknown_arg'"):
        setup_logger("test_invalid_kwargs", unknown_arg=True)


def test_setup_logger_from_config(project_with_marker, reset_chutils_state):
    """Проверяет корректность работы setup_logger_from_config()."""
    from chutils.logger import setup_logger_from_config
    fs, project_root = project_with_marker

    config_content = """
    Logging:
      log_level: WARNING
      log_file_name: test_from_config.log
    """
    fs.create_file(f"{project_root}/config.yml", contents=config_content)

    logger = setup_logger_from_config("logger_from_config", force_reconfigure=True)
    assert logger.name == "logger_from_config"
    assert logger.level == logging.WARNING
