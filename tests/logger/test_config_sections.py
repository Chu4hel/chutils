import logging

from chutils.logger import setup_logger


def test_specific_yaml_section_overrides_general(project_with_marker, reset_chutils_state, mocker):
    """
    Проверяет, что специфичная секция в YAML переопределяет общую [Logging].
    """
    fs, project_root = project_with_marker
    config_content = """
Logging:
  log_level: INFO
  log_file_name: "general.log"
MyAuditLogger:
  log_level: DEBUG
  log_file_name: "audit.log"
"""
    fs.create_file(project_root / "config.yml", contents=config_content)

    mock_handler = mocker.patch("chutils.logger.SafeTimedRotatingFileHandler")
    mock_handler.return_value.level = logging.NOTSET

    logger = setup_logger(
        "some_app",
        config_section_name="MyAuditLogger",
        force_reconfigure=True
    )

    assert logger.level == logging.DEBUG
    mock_handler.assert_called_once()
    call_args = mock_handler.call_args[0][0]
    assert "audit.log" in call_args


def test_fallback_to_general_yaml_section(project_with_marker, reset_chutils_state, mocker):
    """
    Проверяет, что при отсутствии config_section_name используется общая секция [Logging] в YAML.
    """
    fs, project_root = project_with_marker
    config_content = """
Logging:
  log_level: INFO
  log_file_name: "general.log"
MyAuditLogger:
  log_level: DEBUG
  log_file_name: "audit.log"
"""
    fs.create_file(project_root / "config.yml", contents=config_content)

    mock_handler = mocker.patch("chutils.logger.SafeTimedRotatingFileHandler")
    mock_handler.return_value.level = logging.NOTSET

    logger = setup_logger("another_app", force_reconfigure=True)

    assert logger.level == logging.INFO
    mock_handler.assert_called_once()
    call_args = mock_handler.call_args[0][0]
    assert "general.log" in call_args


def test_specific_ini_section_overrides_general(project_with_marker, reset_chutils_state, mocker):
    """
    Проверяет, что специфичная секция в INI переопределяет общую [Logging].
    """
    fs, project_root = project_with_marker
    config_content = """
[Logging]
log_level = INFO
log_file_name = general.log
[MyAuditLogger]
log_level = DEBUG
log_file_name = audit.log
"""
    fs.create_file(project_root / "config.ini", contents=config_content)

    mock_handler = mocker.patch("chutils.logger.SafeTimedRotatingFileHandler")
    mock_handler.return_value.level = logging.NOTSET

    logger = setup_logger(
        "some_app",
        config_section_name="MyAuditLogger",
        force_reconfigure=True
    )

    assert logger.level == logging.DEBUG
    mock_handler.assert_called_once()
    call_args = mock_handler.call_args[0][0]
    assert "audit.log" in call_args


def test_fallback_to_general_ini_section(project_with_marker, reset_chutils_state, mocker):
    """
    Проверяет, что при отсутствии config_section_name используется общая секция [Logging] в INI.
    """
    fs, project_root = project_with_marker
    config_content = """
[Logging]
log_level = INFO
log_file_name = general.log
[MyAuditLogger]
log_level = DEBUG
log_file_name = audit.log
"""
    fs.create_file(project_root / "config.ini", contents=config_content)

    mock_handler = mocker.patch("chutils.logger.SafeTimedRotatingFileHandler")
    mock_handler.return_value.level = logging.NOTSET

    logger = setup_logger("another_app", force_reconfigure=True)

    assert logger.level == logging.INFO
    mock_handler.assert_called_once()
    call_args = mock_handler.call_args[0][0]
    assert "general.log" in call_args
