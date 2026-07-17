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


# Имитируем модули botocore и google.api_core для тестов на окружениях без установленных облачных SDK
import sys
from unittest.mock import MagicMock

if "botocore" not in sys.modules:
    botocore_mock = MagicMock()
    sys.modules["botocore"] = botocore_mock
    sys.modules["botocore.exceptions"] = botocore_mock.exceptions


    # Создаем класс исключения ClientError для моков
    class MockClientError(Exception):
        def __init__(self, error_response, operation_name):
            self.response = error_response
            self.operation_name = operation_name
            super().__init__(str(error_response))


    botocore_mock.exceptions.ClientError = MockClientError

if "google.api_core" not in sys.modules:
    google_mock = MagicMock()
    sys.modules["google"] = google_mock
    sys.modules["google.api_core"] = google_mock.api_core
    sys.modules["google.api_core.exceptions"] = google_mock.api_core.exceptions


    class MockNotFound(Exception):
        pass


    google_mock.api_core.exceptions.NotFound = MockNotFound


def test_aws_provider_get_success(mocker):
    """Проверяет успешное получение секрета из AWS Secrets Manager."""
    mock_boto = mocker.patch("boto3.client")
    mock_client = mock_boto.return_value
    mock_client.get_secret_value.return_value = {"SecretString": "aws_secret_value"}

    from chutils.secret_manager.providers import AWSSecretManagerProvider
    provider = AWSSecretManagerProvider(region_name="us-east-1")
    val = provider.get("my_key", SERVICE_NAME)

    assert val == "aws_secret_value"
    mock_client.get_secret_value.assert_called_once_with(SecretId=f"{SERVICE_NAME}/my_key")


def test_aws_provider_get_not_found(mocker):
    """Проверяет возврат None, если секрет не найден в AWS Secrets Manager."""
    mock_boto = mocker.patch("boto3.client")
    mock_client = mock_boto.return_value

    from botocore.exceptions import ClientError
    error_response = {"Error": {"Code": "ResourceNotFoundException", "Message": "Not Found"}}
    mock_client.get_secret_value.side_effect = ClientError(error_response, "GetSecretValue")

    from chutils.secret_manager.providers import AWSSecretManagerProvider
    provider = AWSSecretManagerProvider()
    val = provider.get("missing_key", SERVICE_NAME)

    assert val is None


def test_aws_provider_set_success(mocker):
    """Проверяет создание нового секрета в AWS Secrets Manager."""
    mock_boto = mocker.patch("boto3.client")
    mock_client = mock_boto.return_value

    from chutils.secret_manager.providers import AWSSecretManagerProvider
    provider = AWSSecretManagerProvider()

    assert provider.set("my_key", "secret_val", SERVICE_NAME) is True
    mock_client.create_secret.assert_called_once_with(
        Name=f"{SERVICE_NAME}/my_key", SecretString="secret_val"
    )


def test_aws_provider_set_already_exists(mocker):
    """Проверяет обновление существующего секрета в AWS Secrets Manager."""
    mock_boto = mocker.patch("boto3.client")
    mock_client = mock_boto.return_value

    from botocore.exceptions import ClientError
    error_response = {"Error": {"Code": "ResourceExistsException", "Message": "Exists"}}
    mock_client.create_secret.side_effect = ClientError(error_response, "CreateSecret")

    from chutils.secret_manager.providers import AWSSecretManagerProvider
    provider = AWSSecretManagerProvider()

    assert provider.set("my_key", "secret_val", SERVICE_NAME) is True
    mock_client.put_secret_value.assert_called_once_with(
        SecretId=f"{SERVICE_NAME}/my_key", SecretString="secret_val"
    )


def test_aws_provider_delete_success(mocker):
    """Проверяет успешное удаление секрета из AWS Secrets Manager."""
    mock_boto = mocker.patch("boto3.client")
    mock_client = mock_boto.return_value

    from chutils.secret_manager.providers import AWSSecretManagerProvider
    provider = AWSSecretManagerProvider()

    assert provider.delete("my_key", SERVICE_NAME) is True
    mock_client.delete_secret.assert_called_once_with(
        SecretId=f"{SERVICE_NAME}/my_key", ForceDeleteWithoutRecovery=True
    )


def test_gcp_provider_get_success(mocker):
    """Проверяет успешное получение секрета из GCP Secret Manager."""
    mock_client_class = mocker.patch("google.cloud.secretmanager.SecretManagerServiceClient")
    mock_client = mock_client_class.return_value

    mock_response = mocker.MagicMock()
    mock_response.payload.data = b"gcp_secret_value"
    mock_client.access_secret_version.return_value = mock_response

    from chutils.secret_manager.providers import GCPSecretManagerProvider
    provider = GCPSecretManagerProvider(project_id="my-project")
    val = provider.get("my_key", SERVICE_NAME)

    assert val == "gcp_secret_value"
    mock_client.access_secret_version.assert_called_once_with(
        request={"name": f"projects/my-project/secrets/{SERVICE_NAME}_my_key/versions/latest"}
    )


def test_gcp_provider_get_not_found(mocker):
    """Проверяет возврат None, если секрет не найден в GCP Secret Manager."""
    mock_client_class = mocker.patch("google.cloud.secretmanager.SecretManagerServiceClient")
    mock_client = mock_client_class.return_value

    from google.api_core.exceptions import NotFound
    mock_client.access_secret_version.side_effect = NotFound("Secret not found")

    from chutils.secret_manager.providers import GCPSecretManagerProvider
    provider = GCPSecretManagerProvider(project_id="my-project")
    val = provider.get("missing_key", SERVICE_NAME)

    assert val is None


def test_gcp_provider_set_new_secret(mocker):
    """Проверяет создание нового секрета в GCP Secret Manager."""
    mock_client_class = mocker.patch("google.cloud.secretmanager.SecretManagerServiceClient")
    mock_client = mock_client_class.return_value

    from google.api_core.exceptions import NotFound
    mock_client.get_secret.side_effect = NotFound("Secret not found")

    from chutils.secret_manager.providers import GCPSecretManagerProvider
    provider = GCPSecretManagerProvider(project_id="my-project")

    assert provider.set("my_key", "secret_val", SERVICE_NAME) is True

    mock_client.create_secret.assert_called_once()
    mock_client.add_secret_version.assert_called_once_with(
        parent="projects/my-project/secrets/test_service_my_key",
        payload={"data": b"secret_val"}
    )


def test_gcp_provider_set_existing_secret(mocker):
    """Проверяет добавление версии для существующего секрета в GCP Secret Manager."""
    mock_client_class = mocker.patch("google.cloud.secretmanager.SecretManagerServiceClient")
    mock_client = mock_client_class.return_value
    mock_client.get_secret.return_value = mocker.MagicMock()

    from chutils.secret_manager.providers import GCPSecretManagerProvider
    provider = GCPSecretManagerProvider(project_id="my-project")

    assert provider.set("my_key", "secret_val", SERVICE_NAME) is True

    mock_client.create_secret.assert_not_called()
    mock_client.add_secret_version.assert_called_once_with(
        parent="projects/my-project/secrets/test_service_my_key",
        payload={"data": b"secret_val"}
    )


def test_gcp_provider_delete_success(mocker):
    """Проверяет удаление секрета из GCP Secret Manager."""
    mock_client_class = mocker.patch("google.cloud.secretmanager.SecretManagerServiceClient")
    mock_client = mock_client_class.return_value

    from chutils.secret_manager.providers import GCPSecretManagerProvider
    provider = GCPSecretManagerProvider(project_id="my-project")

    assert provider.delete("my_key", SERVICE_NAME) is True
    mock_client.delete_secret.assert_called_once_with(
        request={"name": "projects/my-project/secrets/test_service_my_key"}
    )
