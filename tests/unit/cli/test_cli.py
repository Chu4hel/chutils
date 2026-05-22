import sys

import pytest
from chutils.cli import main


def test_cli_secrets_set_parsing(mocker):
    """Проверяет корректность парсинга команды 'secrets set'."""
    mock_sm = mocker.patch("chutils.commands.secrets.SecretManager")
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
    mock_sm = mocker.patch("chutils.commands.secrets.SecretManager")
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
    assert "show-paths" in captured.out
    assert "init" in captured.out
    assert "validate" in captured.out


def test_cli_show_paths(mocker, capsys, monkeypatch):
    """Проверяет работу команды 'show-paths'."""
    # Отключаем Rich для предсказуемого текстового вывода
    monkeypatch.setenv("CH_NO_RICH", "1")

    # Мокаем конфиг, чтобы не зависеть от окружения
    mocker.patch("chutils.config.are_paths_initialized", return_value=True)
    mocker.patch("chutils.config.get_base_dir", return_value="/abs/path/project")
    # Обновляем мок на новую функцию get_all_config_paths
    mocker.patch("chutils.config.get_all_config_paths", return_value=("/abs/path/project/config.yml", None, None))
    # Для обратной совместимости мокаем и старую
    mocker.patch("chutils.config.get_config_paths", return_value=("/abs/path/project/config.yml", None))

    test_args = ["chutils", "show-paths"]
    mocker.patch.object(sys, 'argv', test_args)

    with pytest.raises(SystemExit) as e:
        main()

    assert e.value.code == 0
    captured = capsys.readouterr()
    assert "Корень проекта: /abs/path/project" in captured.out
    assert "Основной конфиг: /abs/path/project/config.yml" in captured.out


def test_cli_show_paths_json(mocker, capsys):
    """Проверяет работу команды 'show-paths --json'."""
    mocker.patch("chutils.config.are_paths_initialized", return_value=True)
    mocker.patch("chutils.config.get_base_dir", return_value="/abs/path/project")
    # Обновляем мок на новую функцию get_all_config_paths
    mocker.patch("chutils.config.get_all_config_paths",
                 return_value=("/abs/path/project/config.yml", None, "/abs/path/project/config.local.yml"))

    test_args = ["chutils", "show-paths", "--json"]
    mocker.patch.object(sys, 'argv', test_args)

    with pytest.raises(SystemExit) as e:
        main()

    assert e.value.code == 0
    captured = capsys.readouterr()
    import json
    data = json.loads(captured.out)
    assert data["base_dir"] == "/abs/path/project"
    assert data["main_config"] == "/abs/path/project/config.yml"


def test_cli_init_non_interactive(mocker, capsys):
    """Проверяет работу команды 'init -y' (неинтерактивной)."""
    mocker.patch("os.path.exists", return_value=False)
    mock_open = mocker.patch("builtins.open", mocker.mock_open())

    test_args = ["chutils", "init", "-y"]
    mocker.patch.object(sys, 'argv', test_args)

    with pytest.raises(SystemExit) as e:
        main()

    assert e.value.code == 0
    captured = capsys.readouterr()
    assert "Инициализация проекта" in captured.out
    assert "[OK] Файл config.yml создан" in captured.out

    # Проверяем, что файлы открывались на запись
    # config.yml и .gitignore
    assert mock_open.call_count >= 2


def test_cli_validate_success(mocker, capsys):
    """Проверяет успешную валидацию."""
    mock_model = mocker.Mock()
    # ИСПРАВЛЕНО: Путь к патчу изменен на новый модульный путь
    mocker.patch("chutils.commands.validate._import_string", return_value=mock_model)
    mocker.patch("chutils.config.get_config", return_value={})

    test_args = ["chutils", "validate", "-m", "myapp.Settings"]
    mocker.patch.object(sys, 'argv', test_args)

    with pytest.raises(SystemExit) as e:
        main()

    assert e.value.code == 0
    captured = capsys.readouterr()
    assert "Конфигурация успешно прошла валидацию" in captured.out


def test_cli_validate_fail(mocker, capsys):
    """Проверяет вывод ошибок при провале валидации."""
    from pydantic import ValidationError

    mock_model = mocker.Mock()
    # ИСПРАВЛЕНО: Путь к патчу изменен на новый модульный путь
    mocker.patch("chutils.commands.validate._import_string", return_value=mock_model)

    # Эмулируем ошибку Pydantic
    mocker.patch("chutils.config.get_config", side_effect=ValidationError.from_exception_data("Model", []))
    # Переопределим errors для простоты теста
    mocker.patch.object(ValidationError, 'errors',
                        return_value=[{'loc': ('Logging', 'level'), 'msg': 'field required'}])

    test_args = ["chutils", "validate", "-m", "myapp.Settings"]
    mocker.patch.object(sys, 'argv', test_args)

    with pytest.raises(SystemExit) as e:
        main()

    assert e.value.code == 1
    captured = capsys.readouterr()
    assert "[FAIL] Ошибки валидации" in captured.out
    assert "Logging -> level: field required" in captured.out
