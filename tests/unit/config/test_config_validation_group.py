import pytest

from chutils.config import validate_required_keys
from chutils.exceptions import ConfigKeyNotFoundError, ConfigValidationGroupError
from chutils.typing import JSONDict


def test_validate_required_keys_success() -> None:
    """Проверяет успешное прохождение валидации, если все ключи присутствуют."""
    config: JSONDict = {
        "Secrets": {
            "telegram_bot_token": "token123",
            "database_url": "postgresql://...",
            "api_key": "key123"
        }
    }
    # Ошибок быть не должно
    validate_required_keys("Secrets", ["telegram_bot_token", "database_url", "api_key"], config=config)


def test_validate_required_keys_failure() -> None:
    """Проверяет выброс ConfigValidationGroupError со списком всех ошибок."""
    config: JSONDict = {
        "Secrets": {
            "telegram_bot_token": "token123",
            # database_url отсутствует
            "api_key": ""  # пустое значение тоже считается ошибкой при required=True
        }
    }

    with pytest.raises(ConfigValidationGroupError) as exc_info:
        validate_required_keys("Secrets", ["telegram_bot_token", "database_url", "api_key"], config=config)

    err = exc_info.value
    assert len(err.exceptions) == 2
    assert isinstance(err.exceptions[0], ConfigKeyNotFoundError)
    assert isinstance(err.exceptions[1], ConfigKeyNotFoundError)

    # Проверяем строковое представление
    err_str = str(err)
    assert "database_url" in err_str
    assert "api_key" in err_str


def test_validate_required_keys_with_dict() -> None:
    """Проверяет работу validate_required_keys при передаче словаря напрямую."""
    data = {"a": 1, "b": "hello"}
    validate_required_keys(data, ["a", "b"])
    validate_required_keys(data, "a")

    with pytest.raises(ConfigValidationGroupError) as exc_info:
        validate_required_keys(data, ["a", "missing"])
    assert "missing" in str(exc_info.value)
