from unittest.mock import MagicMock, patch

import pytest

from chutils.exceptions import ChutilsConfigurationError
from chutils.scraping.captcha.base import BaseCaptchaSolver, BaseAsyncCaptchaSolver


class DummySolver(BaseCaptchaSolver):
    secret_key_name = "DUMMY_API_KEY"


class DummyAsyncSolver(BaseAsyncCaptchaSolver):
    secret_key_name = "DUMMY_API_KEY"


def test_solver_uses_explicit_api_key() -> None:
    """Проверяет, что если API-ключ передан явно, он используется."""
    solver = DummySolver(api_key="explicit_key_123")
    assert solver.api_key == "explicit_key_123"

    async_solver = DummyAsyncSolver(api_key="explicit_key_456")
    assert async_solver.api_key == "explicit_key_456"


def test_solver_retrieves_key_from_secret_manager() -> None:
    """Проверяет получение API-ключа из secret_manager, если он не передан явно."""
    mock_get_secret = MagicMock(return_value="secret_key_from_manager")

    with patch("chutils.secret_manager.SecretManager.get_secret", mock_get_secret):
        solver = DummySolver()
        assert solver.api_key == "secret_key_from_manager"
        mock_get_secret.assert_called_once_with("DUMMY_API_KEY")


def test_solver_raises_configuration_error_when_key_is_missing() -> None:
    """Проверяет, что при отсутствии ключа выбрасывается ChutilsConfigurationError."""
    with patch("chutils.secret_manager.SecretManager.get_secret", return_value=None):
        with pytest.raises(ChutilsConfigurationError) as exc_info:
            DummySolver()
        assert "API-ключ для DummySolver не задан" in str(exc_info.value)
