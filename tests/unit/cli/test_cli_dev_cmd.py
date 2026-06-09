import json
from unittest.mock import MagicMock


def test_cli_dev_no_subcommand(cli_runner):
    """Проверяет вызов без подкоманды."""
    result = cli_runner.invoke(["dev"])
    assert result.exit_code == 0
    assert "Используйте 'chutils dev --help'" in result.stdout


def test_cli_dev_generate_context_markdown(cli_runner):
    """Проверяет генерацию Markdown контекста."""
    result = cli_runner.invoke(["dev", "generate-context"])
    assert result.exit_code == 0
    assert "# Public API Map" in result.stdout
    assert "| Name | Type | Signature | Description |" in result.stdout


def test_cli_dev_generate_context_json(cli_runner):
    """Проверяет генерацию JSON контекста."""
    result = cli_runner.invoke(["dev", "generate-context", "-f", "json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert isinstance(data, list)
    assert len(data) > 0
    assert "name" in data[0]


def test_cli_dev_generate_context_file(cli_runner, config_fs):
    """Проверяет сохранение контекста в файл."""
    fs, project_root = config_fs
    result = cli_runner.invoke(["dev", "generate-context", "-o", "api.md"])
    assert result.exit_code == 0
    assert "Контекст успешно сохранен" in result.stdout
    assert fs.exists("api.md")


def test_cli_dev_generate_tree_success(cli_runner, mocker, config_fs):
    """Проверяет генерацию иерархического индекса (tree)."""
    fs, project_root = config_fs
    mocker.patch("chutils.env.has_pydantic", return_value=True)

    mock_index = MagicMock()
    mock_index.model_dump_json.return_value = '{"nodes": []}'
    mock_indexer = mocker.patch("chutils.dev.ast_indexer.Indexer")
    mock_indexer.return_value.index.return_value = mock_index

    result = cli_runner.invoke(["dev", "generate-context", "--tree"])
    assert result.exit_code == 0
    assert '{"nodes": []}' in result.stdout


def test_cli_dev_generate_tree_no_pydantic(cli_runner, mocker):
    """Проверяет ошибку при отсутствии Pydantic для tree."""
    mocker.patch("chutils.env.has_pydantic", return_value=False)

    result = cli_runner.invoke(["dev", "generate-context", "--tree"])
    assert result.exit_code == 1
    assert "Pydantic is required" in result.stderr or "Pydantic is required" in result.stdout


def test_cli_dev_generate_tree_error(cli_runner, mocker):
    """Проверяет обработку ошибок при генерации tree."""
    mocker.patch("chutils.env.has_pydantic", return_value=True)
    mocker.patch("chutils.dev.ast_indexer.Indexer", side_effect=Exception("AST error"))

    result = cli_runner.invoke(["dev", "generate-context", "--tree"])
    assert result.exit_code == 1
    assert "Ошибка при генерации индекса" in result.stderr or "Ошибка при генерации индекса" in result.stdout
