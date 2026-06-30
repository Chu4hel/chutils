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


def test_cli_dev_ai_lint_success(cli_runner, mocker):
    """Проверяет успешное прохождение проверки ai-lint через CLI."""
    mocker.patch("chutils.dev.ai_lint.LinterEngine.run", return_value=[])
    result = cli_runner.invoke(["dev", "ai-lint"])
    assert result.exit_code == 0
    assert "Все проверки пройдены" in result.stdout


def test_cli_dev_ai_lint_failure(cli_runner, mocker):
    """Проверяет провал проверки ai-lint (наличие ошибок) через CLI."""
    from chutils.dev.ai_lint import LintResult
    mock_error = LintResult(
        rule_name="TestRule",
        message="Critical error detected",
        severity="error",
        file_path="app.py",
        line_number=5
    )
    mocker.patch("chutils.dev.ai_lint.LinterEngine.run", return_value=[mock_error])
    result = cli_runner.invoke(["dev", "ai-lint"])
    assert result.exit_code == 1
    assert "Critical error detected" in result.stdout


def test_cli_dev_ai_lint_soft_mode(cli_runner, mocker):
    """Проверяет --soft-mode флаг, который не должен возвращать ошибку при провале."""
    from chutils.dev.ai_lint import LintResult
    mock_error = LintResult(
        rule_name="TestRule",
        message="Critical error detected",
        severity="error",
        file_path="app.py"
    )
    mocker.patch("chutils.dev.ai_lint.LinterEngine.run", return_value=[mock_error])
    result = cli_runner.invoke(["dev", "ai-lint", "--soft-mode"])
    assert result.exit_code == 0
    assert "Critical error detected" in result.stdout


def test_cli_dev_ai_lint_strict_mode(cli_runner, mocker):
    """Проверяет --strict флаг, который падает при наличии только варнингов."""
    from chutils.dev.ai_lint import LintResult
    mock_warn = LintResult(
        rule_name="TestRule",
        message="Warning detected",
        severity="warn",
        file_path="app.py"
    )
    mocker.patch("chutils.dev.ai_lint.LinterEngine.run", return_value=[mock_warn])

    # Сначала без strict - должен пройти успешно
    res_normal = cli_runner.invoke(["dev", "ai-lint"])
    assert res_normal.exit_code == 0

    # Со strict - должен упасть
    res_strict = cli_runner.invoke(["dev", "ai-lint", "--strict"])
    assert res_strict.exit_code == 1
    assert "Warning detected" in res_strict.stdout


def test_cli_dev_generate_context_project(cli_runner, config_fs):
    """Проверяет генерацию Markdown API карты для внешнего проекта."""
    fs, project_root = config_fs
    project_dir = "/home/user/my_project"
    fs.create_dir(f"{project_dir}/src")
    fs.create_file(f"{project_dir}/src/app.py", contents="""
def my_cool_function(x):
    \"\"\"Документация функции.\"\"\"
    return x
""")

    result = cli_runner.invoke(["dev", "generate-context", "--project", project_dir])
    assert result.exit_code == 0
    assert "# Public API Map: my_project" in result.stdout
    assert "src.app.my_cool_function" in result.stdout


def test_cli_dev_generate_context_project_ignore(cli_runner, config_fs):
    """Проверяет, что .gitignore и .chutilsignore корректно исключают файлы."""
    fs, project_root = config_fs
    project_dir = "/home/user/my_project"
    fs.create_dir(f"{project_dir}/src")
    fs.create_file(f"{project_dir}/src/app.py", contents="def my_func(): pass")
    fs.create_file(f"{project_dir}/src/ignored_file.py", contents="def ignored_func(): pass")
    fs.create_file(f"{project_dir}/src/chutils_ignored.py", contents="def chutils_ignored_func(): pass")

    fs.create_file(f"{project_dir}/.gitignore", contents="ignored_file.py\n")
    fs.create_file(f"{project_dir}/.chutilsignore", contents="chutils_ignored.py\n")

    result = cli_runner.invoke(["dev", "generate-context", "--project", project_dir])
    assert result.exit_code == 0
    assert "src.app.my_func" in result.stdout
    assert "ignored_file" not in result.stdout
    assert "chutils_ignored" not in result.stdout
