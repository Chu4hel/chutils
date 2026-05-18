import sys

import pytest

from chutils.cli import main


def test_cli_secrets_set_parsing(mocker):
    """Проверяет корректность парсинга команды 'secrets set'."""
    mock_sm = mocker.patch("chutils.cli.SecretManager")
    mock_sm.return_value.save_secret.return_value = True

    # Эмулируем аргументы командной строки
    test_args = ["chutils", "secrets", "set", "MY_KEY", "MY_VALUE", "--service", "test_app"]
    mocker.patch.object(sys, 'argv', test_args)

    # ACT
    with pytest.raises(SystemExit) as e:
        main()

    # ASSERT
    assert e.value.code == 0
    mock_sm.assert_called_once_with("test_app")
    mock_sm.return_value.save_secret.assert_called_once_with("MY_KEY", "MY_VALUE")


def test_cli_secrets_delete_parsing(mocker):
    """Проверяет корректность парсинга команды 'secrets delete'."""
    mock_sm = mocker.patch("chutils.cli.SecretManager")
    mock_sm.return_value.delete_secret.return_value = True

    # Эмулируем аргументы командной строки
    test_args = ["chutils", "secrets", "delete", "MY_KEY", "-s", "test_app"]
    mocker.patch.object(sys, 'argv', test_args)

    # ACT
    with pytest.raises(SystemExit) as e:
        main()

    # ASSERT
    assert e.value.code == 0
    mock_sm.assert_called_once_with("test_app")
    mock_sm.return_value.delete_secret.assert_called_once_with("MY_KEY")


def test_cli_help(mocker, capsys):
    """Проверяет вывод справки."""
    test_args = ["chutils", "--help"]
    mocker.patch.object(sys, 'argv', test_args)

    with pytest.raises(SystemExit) as e:
        main()

    assert e.value.code == 0
    captured = capsys.readouterr()
    assert "chutils" in captured.out
    assert "secrets" in captured.out
