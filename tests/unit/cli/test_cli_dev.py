import json
import sys

import pytest
from chutils.cli import main


def test_cli_dev_help(mocker, capsys):
    """Проверяет вывод справки для группы dev."""
    test_args = ["chutils", "dev", "--help"]
    mocker.patch.object(sys, 'argv', test_args)

    with pytest.raises(SystemExit) as e:
        main()

    assert e.value.code == 0
    captured = capsys.readouterr()
    assert "dev" in captured.out
    assert "generate-context" in captured.out


def test_cli_dev_generate_context_markdown(mocker, capsys):
    """Проверяет генерацию контекста в формате Markdown."""
    test_args = ["chutils", "dev", "generate-context", "-f", "markdown"]
    mocker.patch.object(sys, 'argv', test_args)

    with pytest.raises(SystemExit) as e:
        main()

    assert e.value.code == 0
    captured = capsys.readouterr()
    assert "# Public API Map: chutils" in captured.out
    assert "| Name | Type | Signature | Description |" in captured.out
    # Проверяем наличие ключевых функций
    assert "`setup_logger`" in captured.out
    assert "`get_config_value`" in captured.out


def test_cli_dev_generate_context_json(mocker, capsys):
    """Проверяет генерацию контекста в формате JSON."""
    test_args = ["chutils", "dev", "generate-context", "-f", "json"]
    mocker.patch.object(sys, 'argv', test_args)

    with pytest.raises(SystemExit) as e:
        main()

    assert e.value.code == 0
    captured = capsys.readouterr()

    # Пытаемся распарсить JSON (он может быть в середине вывода из-за логов rich)
    # Но обычно main выводит всё в stdout.
    output = captured.out
    # Ищем начало JSON
    json_start = output.find('[')
    if json_start != -1:
        json_str = output[json_start:]
        data = json.loads(json_str)
        assert isinstance(data, list)
        # Проверяем наличие записи для setup_logger
        names = [item["name"] for item in data]
        assert "setup_logger" in names
    else:
        pytest.fail("JSON not found in output")


def test_cli_dev_generate_context_output_file(mocker, tmp_path):
    """Проверяет сохранение контекста в файл."""
    output_file = tmp_path / "api_map.md"
    test_args = ["chutils", "dev", "generate-context", "-o", str(output_file)]
    mocker.patch.object(sys, 'argv', test_args)

    with pytest.raises(SystemExit) as e:
        main()

    assert e.value.code == 0
    assert output_file.exists()
    content = output_file.read_text(encoding="utf-8")
    assert "# Public API Map: chutils" in content
