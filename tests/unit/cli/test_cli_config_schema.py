import json
import sys
from unittest.mock import patch

import pytest
from chutils.cli import main
# Модель для тестов
from pydantic import BaseModel, Field


class CliSchemaModel(BaseModel):
    """Модель для тестирования CLI генерации схемы."""
    cli_field: str = Field(description="CLI Test")


@patch("chutils.config.schema.import_model_class")
@patch("chutils.config.schema.PYDANTIC_AVAILABLE", True)
def test_cli_config_generate_schema_stdout(mock_import, mocker, capsys):
    """Тест вывода схемы в stdout."""
    mock_import.return_value = CliSchemaModel

    test_args = ["chutils", "config", "generate-schema", "--model", "some.module:CliSchemaModel"]
    mocker.patch.object(sys, 'argv', test_args)

    with pytest.raises(SystemExit) as e:
        main()

    assert e.value.code == 0
    captured = capsys.readouterr()

    # Проверяем JSON
    schema = json.loads(captured.out)
    assert schema["title"] == "CliSchemaModel"
    assert "cli_field" in schema["properties"]


@patch("chutils.config.schema.import_model_class")
@patch("chutils.config.schema.PYDANTIC_AVAILABLE", True)
def test_cli_config_generate_schema_output_file(mock_import, mocker, tmp_path, capsys):
    """Тест сохранения схемы в файл через CLI."""
    mock_import.return_value = CliSchemaModel
    output_file = tmp_path / "schema.json"

    test_args = [
        "chutils", "config", "generate-schema",
        "--model", "some.module:CliSchemaModel",
        "--output", str(output_file)
    ]
    mocker.patch.object(sys, 'argv', test_args)

    with pytest.raises(SystemExit) as e:
        main()

    assert e.value.code == 0

    # Проверяем файл
    assert output_file.exists()
    schema = json.loads(output_file.read_text())
    assert schema["title"] == "CliSchemaModel"


@patch("chutils.config.schema.import_model_class")
@patch("chutils.config.schema.PYDANTIC_AVAILABLE", True)
def test_cli_config_generate_schema_error(mock_import, mocker, capsys):
    """Тест обработки ошибок в CLI."""
    mock_import.side_effect = ImportError("Module not found")

    test_args = ["chutils", "config", "generate-schema", "--model", "invalid:Model"]
    mocker.patch.object(sys, 'argv', test_args)

    with pytest.raises(SystemExit) as e:
        main()

    assert e.value.code == 1
    captured = capsys.readouterr()
    assert "Ошибка при генерации схемы" in captured.out
    assert "Module not found" in captured.out
