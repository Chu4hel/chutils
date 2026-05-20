from chutils.secret_manager import SecretManager
from chutils.secret_manager.providers import KeyringProvider, DotEnvProvider, EnvProvider, SecretProvider

SERVICE_NAME = "test_service"


class MockProvider(SecretProvider):
    def __init__(self, name, secrets=None, writable=True):
        self.name = name
        self.secrets = secrets or {}
        self.writable = writable
        self.deleted_keys = []

    def get(self, key, service_name):
        return self.secrets.get(key)

    def set(self, key, value, service_name):
        if self.writable:
            self.secrets[key] = value
            return True
        return False

    def delete(self, key, service_name):
        if key in self.secrets:
            del self.secrets[key]
            self.deleted_keys.append(key)
            return True
        return False


def test_keyring_provider_get(mocker):
    mock_keyring = mocker.patch("chutils.secret_manager.providers.keyring")
    mock_keyring.get_password.return_value = "secret"

    provider = KeyringProvider()
    assert provider.get("key", SERVICE_NAME) == "secret"
    mock_keyring.get_password.assert_called_once_with(SERVICE_NAME, "key")


def test_keyring_provider_set(mocker):
    mock_keyring = mocker.patch("chutils.secret_manager.providers.keyring")

    provider = KeyringProvider()
    assert provider.set("key", "value", SERVICE_NAME) is True
    mock_keyring.set_password.assert_called_once_with(SERVICE_NAME, "key", "value")


def test_keyring_provider_delete(mocker):
    mock_keyring = mocker.patch("chutils.secret_manager.providers.keyring")
    mock_keyring.get_password.return_value = "exists"

    provider = KeyringProvider()
    assert provider.delete("key", SERVICE_NAME) is True
    mock_keyring.delete_password.assert_called_once_with(SERVICE_NAME, "key")


def test_dotenv_provider_get(tmp_path, monkeypatch):
    dotenv = tmp_path / ".env"
    dotenv.write_text("KEY=dotenv_val")

    # Мокаем config.get_base_dir
    monkeypatch.setattr("chutils.config.get_base_dir", lambda: tmp_path)

    provider = DotEnvProvider()
    assert provider.get("KEY", SERVICE_NAME) == "dotenv_val"


def test_env_provider_get(monkeypatch):
    monkeypatch.setenv("SYSTEM_KEY", "env_val")
    provider = EnvProvider()
    assert provider.get("SYSTEM_KEY", SERVICE_NAME) == "env_val"


def test_chain_fallback():
    p1 = MockProvider("p1", {"key2": "val2"})
    p2 = MockProvider("p2", {"key1": "val1", "key2": "wrong"})

    sm = SecretManager(SERVICE_NAME, providers=[p1, p2])

    # key1 should be found in p2
    assert sm.get_secret("key1") == "val1"
    # key2 should be found in p1 (first in chain)
    assert sm.get_secret("key2") == "val2"
    # key3 not found
    assert sm.get_secret("key3") is None


def test_chain_write_first_supported():
    p1 = MockProvider("p1", writable=False)
    p2 = MockProvider("p2", writable=True)

    sm = SecretManager(SERVICE_NAME, providers=[p1, p2])
    assert sm.save_secret("new_key", "new_val") is True

    assert "new_key" not in p1.secrets
    assert p2.secrets["new_key"] == "new_val"


def test_add_provider():
    sm = SecretManager(SERVICE_NAME, providers=[])
    p1 = MockProvider("p1", {"k1": "v1"})
    sm.add_provider(p1)

    assert sm.get_secret("k1") == "v1"
    assert sm.providers == [p1]
