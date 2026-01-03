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


def test_init_fallback_to_project_path(project_with_marker, monkeypatch):
    """
    Проверяет, что если service_name не указан, используется путь к проекту.
    """
    fs, project_root = project_with_marker

    # Полностью сбрасываем состояние модулей, чтобы они переинициализировались
    from chutils import secret_manager, config as chutils_config
    monkeypatch.setattr(secret_manager, '_dotenv_loaded', False)
    monkeypatch.setattr(secret_manager, '_dotenv_values', None)
    monkeypatch.setattr(chutils_config, '_BASE_DIR', None)
    monkeypatch.setattr(chutils_config, '_paths_initialized', False)

    # Переходим в корень фейкового проекта
    import os
    os.chdir(project_root)

    sm = SecretManager("")  # или SecretManager(None)

    # Ожидаем, что service_name будет равен "префикс + путь_к_проекту"
    found_project_path = chutils_config._BASE_DIR
    expected_service_name = sm.prefix + found_project_path
    assert sm.service_name == expected_service_name


def test_save_secret_success(secret_manager, mocker):
    """Проверяет успешное сохранение секрета."""
    mock_set = mocker.patch("chutils.secret_manager.keyring.set_password")
    result = secret_manager.save_secret("my_key", "my_value")
    mock_set.assert_called_once_with(secret_manager.service_name, "my_key", "my_value")
    assert result is True


def test_save_secret_no_keyring_error(secret_manager, mocker):
    """Проверяет обработку ошибки NoKeyringError при сохранении."""
    # Мокаем весь модуль, чтобы избежать побочных эффектов от его внутренней логики
    mock_keyring = mocker.patch("chutils.secret_manager.keyring")
    mock_keyring.set_password.side_effect = NoKeyringError
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
    # Мокаем весь модуль, чтобы избежать побочных эффектов
    mock_keyring = mocker.patch("chutils.secret_manager.keyring")
    mock_keyring.get_password.return_value = "some_value"
    mock_keyring.delete_password.side_effect = PasswordDeleteError

    result = secret_manager.delete_secret("my_key")

    assert result is False


def test_update_secret_is_alias_for_save(secret_manager, mocker):
    """Проверяет, что update_secret является псевдонимом для save_secret."""
    save_mock = mocker.patch.object(secret_manager, 'save_secret')
    secret_manager.update_secret("my_key", "new_value")
    save_mock.assert_called_once_with("my_key", "new_value")


def test_init_with_custom_prefix():
    """Проверяет, что SecretManager можно инициализировать с кастомным префиксом."""
    # Тест с кастомным префиксом
    sm_custom = SecretManager(SERVICE_NAME, prefix="MyPrefix_")
    assert sm_custom.service_name == "MyPrefix_" + SERVICE_NAME

    # Тест с пустым префиксом
    sm_no_prefix = SecretManager(SERVICE_NAME, prefix="")
    assert sm_no_prefix.service_name == SERVICE_NAME


def test_get_secret_from_dotenv(project_with_marker, mocker):
    """
    Проверяет, что секрет может быть получен из .env файла, если его нет в keyring.
    """
    # --- Подготовка ---
    fs, project_root = project_with_marker
    # Создаем фейковый .env файл
    fs.create_file(project_root / ".env", contents="MY_DOTENV_SECRET=dotenv_value")
    # Убеждаемся, что keyring ничего не вернет
    mocker.patch("chutils.secret_manager.keyring.get_password", return_value=None)

    # Сбрасываем состояние модуля, чтобы он пере-загрузил .env
    from chutils import secret_manager
    secret_manager._dotenv_loaded = False
    secret_manager._dotenv_values = None

    # --- Действие ---
    sm = SecretManager("my_app_for_dotenv")
    result = sm.get_secret("MY_DOTENV_SECRET")

    # --- Проверка ---
    assert result == "dotenv_value"


def test_get_secret_prioritizes_keyring(project_with_marker, mocker):
    """
    Проверяет, что keyring имеет приоритет над .env файлом.
    """
    # --- Подготовка ---
    fs, project_root = project_with_marker
    fs.create_file(project_root / ".env", contents="SHARED_SECRET=dotenv_value")
    # Keyring возвращает свое значение
    mocker.patch("chutils.secret_manager.keyring.get_password", return_value="keyring_value")

    # Сбрасываем состояние модуля
    from chutils import secret_manager
    secret_manager._dotenv_loaded = False
    secret_manager._dotenv_values = None

    # --- Действие ---
    sm = SecretManager("my_app_for_dotenv")
    result = sm.get_secret("SHARED_SECRET")

    # --- Проверка ---
    assert result == "keyring_value"
