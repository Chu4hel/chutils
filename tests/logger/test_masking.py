import logging

from chutils.logger import setup_logger


def test_manual_masking(caplog):
    """Проверяет ручное добавление маски."""
    logger = setup_logger("test_manual_masking", log_level="DEBUG")
    # Важно: для pytest caplog нужно, чтобы сообщения доходили до root
    logger.propagate = True

    secret = "P@ssw0rd123"
    logger.add_mask(secret)

    with caplog.at_level(logging.DEBUG):
        logger.info(f"User login with password: {secret}")

    assert secret not in caplog.text
    assert "***" in caplog.text
    assert "User login with password: ***" in caplog.text


def test_multiple_masks(caplog):
    """Проверяет маскирование нескольких разных секретов."""
    logger = setup_logger("test_multiple_masks", log_level="DEBUG")
    logger.propagate = True

    s1, s2 = "secret1", "secret2"
    logger.add_mask(s1)
    logger.add_mask(s2)

    with caplog.at_level(logging.DEBUG):
        logger.info(f"Values: {s1} and {s2}")

    assert s1 not in caplog.text
    assert s2 not in caplog.text
    assert "Values: *** and ***" in caplog.text


def test_masking_disabled_by_env(caplog, monkeypatch):
    """Проверяет отключение маскирования через переменную окружения."""
    monkeypatch.setenv("CH_DISABLE_LOG_MASKING", "true")

    logger = setup_logger("test_env_disabled", log_level="DEBUG")
    logger.propagate = True

    secret = "donotmaskme"
    logger.add_mask(secret)

    with caplog.at_level(logging.DEBUG):
        logger.info(f"Secret is {secret}")

    assert secret in caplog.text
    assert "***" not in caplog.text
