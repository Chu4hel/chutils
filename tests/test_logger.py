
import logging
import pytest
from chutils.logger import setup_logger, ChutilsLogger, MEDIUMDEBUG_LEVEL_NUM, DEVDEBUG_LEVEL_NUM

def test_setup_logger_returns_custom_logger():
    """
    Проверяет, что setup_logger возвращает экземпляр ChutilsLogger.
    """
    logger = setup_logger("test_logger_instance")
    assert isinstance(logger, ChutilsLogger)

def test_custom_log_levels(caplog):
    """
    Проверяет, что кастомные уровни логирования работают корректно.
    """
    logger = setup_logger("test_custom_levels")

    # Сценарий 1: Уровень DEBUG (10)
    # devdebug (9) не должен проходить, остальные - должны
    logger.setLevel(logging.DEBUG)
    with caplog.at_level(DEVDEBUG_LEVEL_NUM):
        logger.devdebug("dev_msg")
        logger.debug("debug_msg")
        logger.mediumdebug("medium_msg")

    assert "dev_msg" not in caplog.text
    assert "debug_msg" in caplog.text
    assert "medium_msg" in caplog.text

    caplog.clear()

    # Сценарий 2: Уровень MEDIUMDEBUG (15)
    # devdebug (9) и debug (10) не должны проходить
    logger.setLevel(MEDIUMDEBUG_LEVEL_NUM)
    with caplog.at_level(DEVDEBUG_LEVEL_NUM):
        logger.devdebug("dev_msg")
        logger.debug("debug_msg")
        logger.mediumdebug("medium_msg")
        logger.info("info_msg")

    assert "dev_msg" not in caplog.text
    assert "debug_msg" not in caplog.text
    assert "medium_msg" in caplog.text
    assert "info_msg" in caplog.text

    caplog.clear()

    # Сценарий 3: Уровень DEVDEBUG (9)
    # Все сообщения должны проходить
    logger.setLevel(DEVDEBUG_LEVEL_NUM)
    with caplog.at_level(DEVDEBUG_LEVEL_NUM):
        logger.devdebug("dev_msg")
        logger.debug("debug_msg")

    assert "dev_msg" in caplog.text
    assert "debug_msg" in caplog.text

