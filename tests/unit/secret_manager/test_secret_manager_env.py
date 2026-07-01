import logging
import os

from keyring.errors import NoKeyringError

from chutils.secret_manager import SecretManager


def test_get_secret_no_keyring_warning(project_with_marker, monkeypatch, caplog):
    """
    Проверяет, что без флага отключения выводится предупреждение при отсутствии keyring.
    """
    fs, project_root = project_with_marker

    def mock_get_password(*args, **kwargs):
        raise NoKeyringError()

    import keyring
    monkeypatch.setattr(keyring, "get_password", mock_get_password)

    # Сбрасываем состояние
    from chutils import config as chutils_config
    chutils_config._cm._reset()

    sm = SecretManager("test_app")
    # Включаем propagation для тестов
    from chutils.secret_manager import providers
    providers._get_logger().propagate = True

    with caplog.at_level(logging.WARNING):
        result = sm.get_secret("ANY_KEY")

    assert result is None
    assert "Keyring не доступен" in caplog.text


def test_get_secret_suppress_keyring_warning_via_env(project_with_marker, monkeypatch, caplog):
    """
    Проверяет, что при CH_DISABLE_KEYRING_WARNING=true предупреждение подавляется.
    """
    fs, project_root = project_with_marker

    called = False

    def mock_get_password(*args, **kwargs):
        nonlocal called
        called = True
        return None

    import keyring
    monkeypatch.setattr(keyring, "get_password", mock_get_password)

    os.environ["CH_DISABLE_KEYRING_WARNING"] = "true"
    try:
        # Сбрасываем состояние
        from chutils import config as chutils_config
        chutils_config._cm._reset()

        sm = SecretManager("test_app")
        from chutils.secret_manager import providers
        providers._get_logger().propagate = True

        with caplog.at_level(logging.WARNING):
            result = sm.get_secret("ANY_KEY")

        assert result is None
        # Проверяем, что предупреждение НЕ выводилось
        assert "Keyring не доступен" not in caplog.text
        # Проверяем, что к keyring вообще не обращались
        assert not called
    finally:
        if "CH_DISABLE_KEYRING_WARNING" in os.environ:
            del os.environ["CH_DISABLE_KEYRING_WARNING"]


def test_get_secret_suppress_keyring_warning_via_config(project_with_marker, monkeypatch, caplog):
    """
    Проверяет, что при disable_keyring: true в конфиге предупреждение подавляется.
    """
    fs, project_root = project_with_marker

    called = False

    def mock_get_password(*args, **kwargs):
        nonlocal called
        called = True
        return None

    import keyring
    monkeypatch.setattr(keyring, "get_password", mock_get_password)

    content = """
secrets:
  disable_keyring: true
"""
    fs.create_file(project_root / "config.yml", contents=content)

    # Сбрасываем состояние
    from chutils import config as chutils_config
    chutils_config._cm._reset()

    # Переходим в корень фейкового проекта для автообнаружения конфига
    os.chdir(project_root)

    sm = SecretManager("test_app")
    from chutils.secret_manager import providers
    providers._get_logger().propagate = True

    with caplog.at_level(logging.WARNING):
        result = sm.get_secret("ANY_KEY")

    assert result is None
    # Проверяем, что предупреждение НЕ выводилось
    assert "Keyring не доступен" not in caplog.text
    # Проверяем, что к keyring вообще не обращались
    assert not called

