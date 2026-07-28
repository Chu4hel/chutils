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
    assert "[MASKED]" in caplog.text
    assert "User login with password: [MASKED]" in caplog.text


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
    assert "Values: [MASKED] and [MASKED]" in caplog.text


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
    assert "[MASKED]" not in caplog.text


def test_secret_masking_filter_direct():
    """Проверяет прямой вызов SecretMaskingFilter и передачу secrets в конструктор."""
    from chutils.logger import SecretMaskingFilter, register_secret_mask, clear_masks

    clear_masks()
    filter_obj = SecretMaskingFilter(secrets=["SecretPass123!"])
    record = logging.LogRecord(
        name="app", level=logging.INFO, pathname="", lineno=0,
        msg="User login with password SecretPass123!", args=(), exc_info=None
    )
    filter_obj.filter(record)
    assert record.msg == "User login with password [MASKED]"

    register_secret_mask("AnotherSecret")
    record2 = logging.LogRecord(
        name="app", level=logging.INFO, pathname="", lineno=0,
        msg="Data: AnotherSecret", args=(), exc_info=None
    )
    filter_obj.filter(record2)
    assert record2.msg == "Data: [MASKED]"
    clear_masks()

