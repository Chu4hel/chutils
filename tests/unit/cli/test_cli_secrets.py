def test_cli_secrets_set_success(cli_runner, mocker):
    """Проверяет успешное сохранение секрета."""
    mock_sm = mocker.patch("chutils.commands.secrets.SecretManager")
    mock_sm.return_value.save_secret.return_value = True

    result = cli_runner.invoke(["secrets", "set", "MY_KEY", "MY_VAL", "-s", "test_app"])

    assert result.exit_code == 0
    assert "успешно сохранен" in result.stdout
    mock_sm.assert_called_with("test_app")
    mock_sm.return_value.save_secret.assert_called_with("MY_KEY", "MY_VAL")


def test_cli_secrets_set_fail(cli_runner, mocker):
    """Проверяет ошибку при сохранении секрета."""
    mock_sm = mocker.patch("chutils.commands.secrets.SecretManager")
    mock_sm.return_value.save_secret.return_value = False

    result = cli_runner.invoke(["secrets", "set", "MY_KEY", "MY_VAL"])

    assert result.exit_code == 1
    assert "Не удалось сохранить секрет" in result.stderr or "Не удалось сохранить секрет" in result.stdout


def test_cli_secrets_delete_success(cli_runner, mocker):
    """Проверяет успешное удаление секрета."""
    mock_sm = mocker.patch("chutils.commands.secrets.SecretManager")
    mock_sm.return_value.delete_secret.return_value = True

    result = cli_runner.invoke(["secrets", "delete", "MY_KEY", "--service", "test_app"])

    assert result.exit_code == 0
    assert "успешно удален" in result.stdout
    mock_sm.assert_called_with("test_app")
    mock_sm.return_value.delete_secret.assert_called_with("MY_KEY")


def test_cli_secrets_delete_fail(cli_runner, mocker):
    """Проверяет ошибку при удалении секрета."""
    mock_sm = mocker.patch("chutils.commands.secrets.SecretManager")
    mock_sm.return_value.delete_secret.return_value = False

    result = cli_runner.invoke(["secrets", "delete", "MY_KEY"])

    assert result.exit_code == 1
    assert "Не удалось удалить секрет" in result.stderr or "Не удалось удалить секрет" in result.stdout


def test_cli_secrets_no_subcommand(cli_runner):
    """Проверяет вызов без подкоманды."""
    result = cli_runner.invoke(["secrets"])
    assert result.exit_code == 0
    assert "Используйте 'chutils secrets --help'" in result.stdout


def test_cli_secrets_error_handling(cli_runner, mocker):
    """Проверяет обработку SecretError."""
    from chutils.exceptions import SecretError
    mock_sm = mocker.patch("chutils.commands.secrets.SecretManager")
    mock_sm.return_value.save_secret.side_effect = SecretError("Secret storage error", hint="Unlock your keyring")

    result = cli_runner.invoke(["secrets", "set", "K", "V"])

    assert result.exit_code == 1
    assert "Secret storage error" in result.stderr or "Secret storage error" in result.stdout
    # Проверка подсказки (в stderr она может быть без тегов)
    assert "Unlock your keyring" in result.stderr or "Unlock your keyring" in result.stdout


def test_cli_secrets_keyring_not_available(cli_runner, monkeypatch):
    """Проверяет поведение CLI secrets при отсутствии keyring."""
    monkeypatch.setattr("chutils.secret_manager.providers.KEYRING_AVAILABLE", False)

    # 1. Попытка вызова set
    result = cli_runner.invoke(["secrets", "set", "K", "V"])
    assert result.exit_code == 1
    assert "Missing optional dependency: please install chutils[keyring]" in (result.stderr + result.stdout)

    # 2. Попытка вызова delete
    result = cli_runner.invoke(["secrets", "delete", "K"])
    assert result.exit_code == 1
    assert "Missing optional dependency: please install chutils[keyring]" in (result.stderr + result.stdout)

    # 3. Попытка вызова просто secrets
    result = cli_runner.invoke(["secrets"])
    assert result.exit_code == 1
    assert "Missing optional dependency: please install chutils[keyring]" in (result.stderr + result.stdout)
