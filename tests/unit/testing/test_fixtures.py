from chutils.config import get_config_value, get_config_int
from chutils.context import bind_context, clear_context
from chutils.logger import setup_logger
from chutils.secret_manager.core import SecretManager
from chutils.testing.fixtures import mock_chutils_config, mock_chutils_secrets, capture_chutils_logs


def test_mock_chutils_config_basic(mock_chutils_config):
    """Проверка базовой установки значений конфигурации."""
    mock_chutils_config.set("test", "key", "value")
    mock_chutils_config.set("test", "port", 8080)

    assert get_config_value("test", "key") == "value"
    assert get_config_int("test", "port") == 8080


def test_mock_chutils_config_load(mock_chutils_config):
    """Проверка загрузки всей конфигурации из словаря."""
    data = {
        "database": {"host": "localhost", "user": "admin"},
        "logging": {"level": "DEBUG"}
    }
    mock_chutils_config.load(data)

    assert get_config_value("database", "host") == "localhost"
    assert get_config_value("logging", "level") == "DEBUG"


def test_mock_chutils_secrets_basic(mock_chutils_secrets):
    """Проверка мокирования секретов."""
    mock_chutils_secrets.set_secret("api_token", "super-secret")

    sm = SecretManager(service_name="test_service")
    assert sm.get_secret("api_token") == "super-secret"
    assert sm.get_secret("non_existent") is None


def test_mock_chutils_secrets_isolation(mock_chutils_secrets):
    """Проверка того, что SecretManager использует только мокированный провайдер."""
    sm = SecretManager(service_name="test_service")
    sm.save_secret("new_secret", "new-value")

    assert mock_chutils_secrets.get("new_secret", "any") == "new-value"
    assert len(sm.providers) == 1


def test_capture_chutils_logs_basic(capture_chutils_logs):
    """Проверка базового перехвата сообщений."""
    logger = setup_logger("test_logger")
    logger.info("Hello fixture world")

    assert capture_chutils_logs.has_message("Hello fixture world")
    assert capture_chutils_logs.has_message("fixture", partial=True)
    assert not capture_chutils_logs.has_message("Goodbye")


def test_capture_chutils_logs_fields(capture_chutils_logs):
    """Проверка фильтрации логов по полям (контексту)."""
    clear_context()
    logger = setup_logger("context_logger")

    bind_context(request_id="abc-123", user="bob")
    logger.warning("Something happened")

    bind_context(request_id="def-456", user="alice")
    logger.error("Error occurred")

    # Проверка поиска по полям
    records_bob = capture_chutils_logs.get_by_field("user", "bob")
    assert len(records_bob) == 1
    assert "Something happened" in records_bob[0].getMessage()
    assert records_bob[0].request_id == "abc-123"

    records_alice = capture_chutils_logs.get_by_field("request_id", "def-456")
    assert len(records_alice) == 1
    assert records_alice[0].user == "alice"


def test_capture_chutils_logs_clear(capture_chutils_logs):
    """Проверка очистки перехваченных логов."""
    logger = setup_logger("clear_logger")
    logger.info("Message 1")
    assert len(capture_chutils_logs.records) == 1

    capture_chutils_logs.clear()
    assert len(capture_chutils_logs.records) == 0

    logger.info("Message 2")
    assert len(capture_chutils_logs.records) == 1
    assert capture_chutils_logs.records[0].getMessage() == "Message 2"
