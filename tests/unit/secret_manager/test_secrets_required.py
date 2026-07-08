"""Тесты для параметров fallback и required в SecretManager.get_secret / aget_secret."""
import pytest

from chutils.exceptions import SecretNotFoundError
from chutils.secret_manager import SecretManager

SERVICE_NAME = "test_secrets_required"


@pytest.fixture
def sm(mocker):
    """SecretManager с мок-провайдером, у которого нет секретов."""
    mocker.patch("chutils.secret_manager.core._warn_about_missing_keyring")
    from chutils.secret_manager.providers import EnvProvider
    return SecretManager(SERVICE_NAME, providers=[EnvProvider()])


class TestGetSecretFallback:
    """Тесты параметра fallback."""

    def test_returns_none_when_not_found_no_fallback(self, sm, monkeypatch):
        """get_secret возвращает None, если секрет не найден и fallback не указан."""
        monkeypatch.delenv(f"Chutils_{SERVICE_NAME}_MISSING_KEY", raising=False)
        result = sm.get_secret("MISSING_KEY")
        assert result is None

    def test_returns_fallback_when_not_found(self, sm, monkeypatch):
        """get_secret возвращает fallback, если секрет не найден."""
        monkeypatch.delenv(f"Chutils_{SERVICE_NAME}_MISSING_KEY", raising=False)
        result = sm.get_secret("MISSING_KEY", fallback="default_value")
        assert result == "default_value"

    def test_returns_value_when_found_ignoring_fallback(self, sm, monkeypatch):
        """get_secret возвращает реальное значение, игнорируя fallback."""
        monkeypatch.setenv("MISSING_KEY", "real_value")
        result = sm.get_secret("MISSING_KEY", fallback="default_value")
        assert result == "real_value"


class TestGetSecretRequired:
    """Тесты параметра required."""

    def test_raises_when_required_and_not_found(self, sm, monkeypatch):
        """get_secret выбрасывает SecretNotFoundError при required=True и отсутствии секрета."""
        monkeypatch.delenv(f"Chutils_{SERVICE_NAME}_TOTALLY_MISSING", raising=False)
        with pytest.raises(SecretNotFoundError) as exc_info:
            sm.get_secret("TOTALLY_MISSING", required=True)
        assert "TOTALLY_MISSING" in exc_info.value.message

    def test_returns_value_when_required_and_found(self, sm, monkeypatch):
        """get_secret возвращает значение при required=True, если секрет найден."""
        monkeypatch.setenv("EXISTING_KEY", "secret_val")
        result = sm.get_secret("EXISTING_KEY", required=True)
        assert result == "secret_val"

    def test_required_ignores_fallback(self, sm, monkeypatch):
        """При required=True fallback не используется — выбрасывается ошибка."""
        monkeypatch.delenv(f"Chutils_{SERVICE_NAME}_MISSING", raising=False)
        with pytest.raises(SecretNotFoundError):
            sm.get_secret("MISSING", fallback="ignored", required=True)


class TestAgetSecretFallbackRequired:
    """Тесты для асинхронного aget_secret."""

    @pytest.mark.asyncio
    async def test_aget_returns_fallback(self, sm, monkeypatch):
        """aget_secret возвращает fallback, если секрет не найден."""
        monkeypatch.delenv(f"Chutils_{SERVICE_NAME}_ASYNC_MISS", raising=False)
        result = await sm.aget_secret("ASYNC_MISS", fallback="async_default")
        assert result == "async_default"

    @pytest.mark.asyncio
    async def test_aget_raises_when_required(self, sm, monkeypatch):
        """aget_secret выбрасывает SecretNotFoundError при required=True."""
        monkeypatch.delenv(f"Chutils_{SERVICE_NAME}_ASYNC_REQ", raising=False)
        with pytest.raises(SecretNotFoundError):
            await sm.aget_secret("ASYNC_REQ", required=True)

    @pytest.mark.asyncio
    async def test_aget_returns_value_when_found(self, sm, monkeypatch):
        """aget_secret возвращает значение, если секрет найден."""
        monkeypatch.setenv("ASYNC_FOUND", "found_val")
        result = await sm.aget_secret("ASYNC_FOUND", required=True)
        assert result == "found_val"
