import pytest
from chutils.secret_manager import SecretManager, NoKeyringError, PasswordDeleteError

SERVICE_NAME = "my_test_app"

@pytest.fixture
def secret_manager():
    """
    Фикстура, возвращающая экземпляр SecretManager.
    """
    return SecretManager(SERVICE_NAME)

def test_init_success(secret_manager):
    """Проверяет успешную инициализацию SecretManager."""
    assert secret_manager.service_name == SecretManager.prefix + SERVICE_NAME

def test_init_failure():
    """Проверяет, что инициализация с некорректным service_name вызывает ошибку."""
    with pytest.raises(ValueError):
        SecretManager("")
    with pytest.raises(ValueError):
        SecretManager(None) # type: ignore

def test_save_secret_success(secret_manager, mocker):
    """Проверяет успешное сохранение секрета."""
    mock_set = mocker.patch("chutils.secret_manager.keyring.set_password")
    result = secret_manager.save_secret("my_key", "my_value")
    mock_set.assert_called_once_with(secret_manager.service_name, "my_key", "my_value")
    assert result is True

def test_save_secret_no_keyring_error(secret_manager, mocker):
    """Проверяет обработку ошибки NoKeyringError при сохранении."""
    mocker.patch("chutils.secret_manager.keyring.set_password", side_effect=NoKeyringError)
    result = secret_manager.save_secret("my_key", "my_value")
    assert result is False

def test_get_secret_success(secret_manager, mocker):
    """Проверяет успешное получение существующего секрета."""
    mock_get = mocker.patch("chutils.secret_manager.keyring.get_password")
    mock_get.return_value = "my_secret_value"
    result = secret_manager.get_secret("my_key")
    mock_get.assert_called_once_with(secret_manager.service_name, "my_key")
    assert result == "my_secret_value"

def test_get_secret_not_found(secret_manager, mocker):
    """Проверяет получение несуществующего секрета."""
    mock_get = mocker.patch("chutils.secret_manager.keyring.get_password")
    mock_get.return_value = None
    result = secret_manager.get_secret("non_existent_key")
    assert result is None

def test_delete_secret_success(secret_manager, mocker):
    """Проверяет успешное удаление секрета."""
    mock_get = mocker.patch("chutils.secret_manager.keyring.get_password", return_value="some_value")
    mock_delete = mocker.patch("chutils.secret_manager.keyring.delete_password")
    
    result = secret_manager.delete_secret("my_key")
    
    mock_get.assert_called_once_with(secret_manager.service_name, "my_key")
    mock_delete.assert_called_once_with(secret_manager.service_name, "my_key")
    assert result is True


def test_delete_secret_not_found(secret_manager, mocker):
    """Проверяет удаление несуществующего секрета."""
    mock_get = mocker.patch("chutils.secret_manager.keyring.get_password", return_value=None)
    mock_delete = mocker.patch("chutils.secret_manager.keyring.delete_password")

    result = secret_manager.delete_secret("non_existent_key")

    mock_get.assert_called_once_with(secret_manager.service_name, "non_existent_key")
    mock_delete.assert_not_called()
    assert result is True

def test_delete_secret_error(secret_manager, mocker):
    """Проверяет обработку ошибки при удалении."""
    mocker.patch("chutils.secret_manager.keyring.get_password", return_value="some_value")
    mocker.patch("chutils.secret_manager.keyring.delete_password", side_effect=PasswordDeleteError)
    
    result = secret_manager.delete_secret("my_key")
    
    assert result is False

def test_update_secret_is_alias_for_save(secret_manager, mocker):
    """Проверяет, что update_secret является псевдонимом для save_secret."""
    save_mock = mocker.patch.object(secret_manager, 'save_secret')
    secret_manager.update_secret("my_key", "new_value")
    save_mock.assert_called_once_with("my_key", "new_value")