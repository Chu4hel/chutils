import logging
import os

from chutils.secret_manager import SecretManager, NoKeyringError


def test_get_secret_no_keyring_warning(project_with_marker, mocker, caplog):
    """
    Проверяет, что без флага отключения выводится предупреждение при отсутствии keyring.
    """
    fs, project_root = project_with_marker
    mocker.patch("chutils.secret_manager.keyring.get_password", side_effect=NoKeyringError)

    # Сбрасываем состояние модуля
    from chutils import secret_manager
    secret_manager._dotenv_loaded = False
    secret_manager._dotenv_values = None
    secret_manager._module_logger = None  # Сбрасываем логгер

    sm = SecretManager("test_app")
    # Включаем propagation для тестов, так как setup_logger его выключает
    secret_manager._get_logger().propagate = True

    with caplog.at_level(logging.WARNING):
        result = sm.get_secret("ANY_KEY")

    assert result is None
    assert "Keyring не доступен" in caplog.text


def test_get_secret_suppress_keyring_warning_via_env(project_with_marker, mocker, caplog):
    """
    Проверяет, что при CH_DISABLE_KEYRING_WARNING=true предупреждение подавляется.
    """
    fs, project_root = project_with_marker
    mock_get = mocker.patch("chutils.secret_manager.keyring.get_password")

    os.environ["CH_DISABLE_KEYRING_WARNING"] = "true"
    try:
        # Сбрасываем состояние модуля
        from chutils import secret_manager, config
        secret_manager._dotenv_loaded = False
        secret_manager._dotenv_values = None
        secret_manager._module_logger = None
        config._config_loaded = False
        config._config_object = None

        sm = SecretManager("test_app")
        secret_manager._get_logger().propagate = True

        with caplog.at_level(logging.WARNING):
            result = sm.get_secret("ANY_KEY")

        assert result is None
        # Проверяем, что предупреждение НЕ выводилось
        assert "Keyring не доступен" not in caplog.text
        # Проверяем, что к keyring вообще не обращались
        mock_get.assert_not_called()
    finally:
        if "CH_DISABLE_KEYRING_WARNING" in os.environ:
            del os.environ["CH_DISABLE_KEYRING_WARNING"]


def test_get_secret_suppress_keyring_warning_via_config(project_with_marker, mocker, caplog):
    """
    Проверяет, что при disable_keyring: true в конфиге предупреждение подавляется.
    """
    fs, project_root = project_with_marker
    mock_get = mocker.patch("chutils.secret_manager.keyring.get_password")

    content = """
secrets:
  disable_keyring: true
"""
    fs.create_file(project_root / "config.yml", contents=content)

    # Сбрасываем состояние модуля
    from chutils import secret_manager, config
    secret_manager._dotenv_loaded = False
    secret_manager._dotenv_values = None
    secret_manager._module_logger = None
    config._config_loaded = False
    config._config_object = None
    config._paths_initialized = False

    # Переходим в корень фейкового проекта для автообнаружения конфига
    os.chdir(project_root)

    sm = SecretManager("test_app")
    secret_manager._get_logger().propagate = True

    with caplog.at_level(logging.WARNING):
        result = sm.get_secret("ANY_KEY")

    assert result is None
    # Проверяем, что предупреждение НЕ выводилось
    assert "Keyring не доступен" not in caplog.text
    # Проверяем, что к keyring вообще не обращались
    mock_get.assert_not_called()
