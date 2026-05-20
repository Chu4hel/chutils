import logging

from chutils.logger import setup_logger
from chutils.secret_manager import SecretManager


def test_secret_manager_masking_integration(caplog, monkeypatch):
    """
    Интеграционный тест: SecretManager должен автоматически добавлять секреты в маску логгера.
    """
    # 1. Настраиваем окружение
    secret_key = "MY_DB_PASSWORD"
    secret_value = "SuperSecret_12345"
    monkeypatch.setenv(secret_key, secret_value)

    # Сбрасываем глобальные маски для чистоты теста
    from chutils.logger import masking as chutils_masking
    chutils_masking._GLOBAL_MASKS.clear()
    chutils_masking._update_mask_re()

    # 2. Инициализируем SecretManager и получаем секрет
    sm = SecretManager("test_service")
    val = sm.get_secret(secret_key)
    assert val == secret_value

    # 3. Проверяем логирование через любой логгер chutils
    logger = setup_logger("test_integration")
    logger.propagate = True

    with caplog.at_level(logging.INFO):
        logger.info(f"Connecting with password: {secret_value}")

    assert secret_value not in caplog.text
    assert "***" in caplog.text
    assert "Connecting with password: ***" in caplog.text


def test_secret_manager_masking_opt_out(caplog, monkeypatch):
    """
    Проверяет возможность отключения автоматического маскирования в SecretManager.
    """
    secret_key = "OPT_OUT_SECRET"
    secret_value = "VisibleSecret_999"
    monkeypatch.setenv(secret_key, secret_value)

    from chutils.logger import masking as chutils_masking
    chutils_masking._GLOBAL_MASKS.clear()
    chutils_masking._update_mask_re()

    # Инициализируем с auto_mask_logs=False
    sm = SecretManager("test_opt_out", auto_mask_logs=False)
    sm.get_secret(secret_key)

    logger = setup_logger("test_no_mask")
    logger.propagate = True

    with caplog.at_level(logging.INFO):
        logger.info(f"Secret value: {secret_value}")

    assert secret_value in caplog.text
    assert "***" not in caplog.text
