def test_cli_config_no_subcommand(cli_runner):
    """Проверяет вызов без подкоманды."""
    result = cli_runner.invoke(["config"])
    assert result.exit_code == 0
    assert "Используйте 'chutils config --help'" in result.stdout


def test_cli_config_debug_table(cli_runner, config_fs):
    """Проверяет формат table в config debug."""
    fs, project_root = config_fs
    fs.create_file("config.yml", contents="logging:\n  level: INFO")

    result = cli_runner.invoke(["config", "debug", "--format", "table"])
    assert result.exit_code == 0
    assert "История источников" in result.stdout or "logging" in result.stdout.lower()


def test_cli_config_debug_with_model(cli_runner, config_fs, mocker):
    """Проверяет config debug с указанием модели."""
    fs, project_root = config_fs
    from pydantic import BaseModel
    class Settings(BaseModel):
        app_name: str = "TestApp"

    mocker.patch("chutils.config.schema.import_model_class", return_value=Settings)

    result = cli_runner.invoke(["config", "debug", "--model", "myapp:Settings", "--defaults"])
    assert result.exit_code == 0
    assert "default" in result.stdout


def test_cli_config_debug_import_error(cli_runner, mocker):
    """Проверяет ошибку импорта модели в config debug."""
    mocker.patch("chutils.config.schema.import_model_class", side_effect=Exception("Import fail"))

    result = cli_runner.invoke(["config", "debug", "--model", "bad:Model"])
    assert result.exit_code == 1
    assert "Ошибка при импорте модели" in result.stderr or "Ошибка при импорте модели" in result.stdout


def test_cli_config_generate_schema_stdout(cli_runner, mocker):
    """Проверяет генерацию схемы в stdout."""
    mocker.patch("chutils.config.export_schema", return_value='{"title": "Schema"}')

    result = cli_runner.invoke(["config", "generate-schema", "--model", "m:M"])
    assert result.exit_code == 0
    assert '{"title": "Schema"}' in result.stdout


def test_cli_config_generate_schema_file(cli_runner, config_fs, mocker):
    """Проверяет генерацию схемы в файл."""
    fs, project_root = config_fs

    def mock_export(model, output_path=None):
        if output_path:
            fs.create_file(output_path, contents='{"title": "Schema"}')
        return '{"title": "Schema"}'

    mocker.patch("chutils.config.export_schema", side_effect=mock_export)

    result = cli_runner.invoke(["config", "generate-schema", "--model", "m:M", "-o", "schema.json"])
    assert result.exit_code == 0
    assert "успешно сохранена" in result.stdout
    assert fs.exists("schema.json")


def test_cli_config_generate_schema_error(cli_runner, mocker):
    """Проверяет ошибку при генерации схемы."""
    mocker.patch("chutils.config.export_schema", side_effect=Exception("Schema error"))

    result = cli_runner.invoke(["config", "generate-schema", "--model", "m:M"])
    assert result.exit_code == 1
    assert "Ошибка при генерации схемы" in result.stderr or "Ошибка при генерации схемы" in result.stdout


def test_cli_config_debug_include_fallbacks(cli_runner, project_with_marker, mocker):
    """Проверяет config debug с флагом --include-fallbacks."""
    fs, project_root = project_with_marker
    mocker.patch(
        "chutils.config.ast_fallback_parser.parse_fallbacks_from_project",
        return_value={"SectionFromCode": {"key_from_code": "code_fallback_val"}}
    )

    result = cli_runner.invoke(["config", "debug", "--include-fallbacks"])
    assert result.exit_code == 0
    assert "default" in result.stdout
    assert "sectionfromcode" in result.stdout
    # Для секретов (или при выводе без --show-secrets) значение может маскироваться,
    # но "masked" должно присутствовать, так как "default" вывелся.
    # Проверим, что значение было записано и маскировано:
    assert "[MASKED]" in result.stdout
