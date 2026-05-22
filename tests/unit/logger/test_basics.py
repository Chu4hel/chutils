import logging

from chutils import setup_logger, ChutilsLogger
from chutils.logger import DEVDEBUG_LEVEL_NUM, MEDIUMDEBUG_LEVEL_NUM


def test_setup_logger_returns_custom_logger(config_fs):
    """
    Проверяет, что setup_logger возвращает экземпляр ChutilsLogger.
    """
    logger = setup_logger("test_logger_instance")
    assert isinstance(logger, ChutilsLogger)


def test_custom_log_levels(config_fs, caplog):
    """
    Проверяет, что кастомные уровни логирования работают корректно.
    """
    logger = setup_logger("test_custom_levels")

    # caplog слушает RootLogger, поэтому для теста нам нужно включить передачу наверх.
    logger.propagate = True

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


def test_logger_does_not_propagate_to_root(caplog):
    """
    Проверяет, что логгер НЕ передает сообщения корневому логгеру.
    Это гарантирует отсутствие двойного логирования в консоли приложения.
    """
    # 1. Создаем логгер
    logger = setup_logger("test_propagation_logger", force_reconfigure=True)

    # 2. Проверяем атрибут (явная проверка настройки)
    assert logger.propagate is False, "Атрибут propagate должен быть False"

    # 3. Проверяем поведение (функциональная проверка)
    # caplog автоматически перехватывает сообщения, идущие в Root Logger.
    # Так как propagate=False, сообщение НЕ должно попасть в caplog.
    unique_msg = "This message should NOT appear in caplog"

    logger.info(unique_msg)

    # Важно: мы ожидаем, что сообщения НЕТ в перехваченных логах
    assert unique_msg not in caplog.text
