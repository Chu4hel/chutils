import json
import sys

import pytest

from chutils.cli import main


def test_cli_config_debug_json(mocker, config_fs, capsys):
    """Проверяет работу команды 'chutils config debug --format json'."""
    fs, project_root = config_fs
    config_content = """
    App:
      name: "TestApp"
    """
    fs.create_file(project_root / "config.yml", contents=config_content)

    # Эмулируем аргументы
    test_args = ["chutils", "config", "debug", "--format", "json"]
    mocker.patch.object(sys, 'argv', test_args)

    # ACT
    with pytest.raises(SystemExit) as e:
        main()

    # ASSERT
    assert e.value.code == 0
    captured = capsys.readouterr()

    # Проверяем, что вывелся валидный JSON
    data = json.loads(captured.out)
    assert "app" in data
    assert data["app"]["name"][0]["value"] == "TestApp"
    assert data["app"]["name"][0]["source"].endswith("config.yml")


def test_cli_config_debug_tree(mocker, config_fs, capsys):
    """Проверяет работу команды 'chutils config debug' (формат по умолчанию tree)."""
    fs, project_root = config_fs
    fs.create_file(project_root / "config.yml", contents="App:\n  name: Test")

    test_args = ["chutils", "config", "debug"]
    mocker.patch.object(sys, 'argv', test_args)

    with pytest.raises(SystemExit) as e:
        main()

    assert e.value.code == 0
    captured = capsys.readouterr()
    # Даже если Rich не установлен, мы выводим как таблицу/список
    assert "App" in captured.out or "app" in captured.out
    assert "name" in captured.out
    assert "Test" in captured.out


def test_cli_config_debug_masking(mocker, config_fs, capsys):
    """Проверяет маскирование в CLI."""
    fs, project_root = config_fs
    fs.create_file(project_root / "config.yml", contents="Secrets:\n  api_key: secret123")

    # Без флага --show-secrets
    test_args = ["chutils", "config", "debug", "--format", "json"]
    mocker.patch.object(sys, 'argv', test_args)

    with pytest.raises(SystemExit) as e:
        main()

    captured = capsys.readouterr()
    assert "[MASKED]" in captured.out
    assert "secret123" not in captured.out

    # С флагом --show-secrets
    test_args_show = ["chutils", "config", "debug", "--format", "json", "--show-secrets"]
    mocker.patch.object(sys, 'argv', test_args_show)

    with pytest.raises(SystemExit) as e:
        main()

    captured_show = capsys.readouterr()
    assert "secret123" in captured_show.out
    assert "[MASKED]" not in captured_show.out
