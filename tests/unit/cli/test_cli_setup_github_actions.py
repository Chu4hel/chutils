from __future__ import annotations


def test_cli_setup_github_actions_no_interactive_default(cli_runner, config_fs):
    """Проверяет CLI-команду с флагом --no-interactive и дефолтными значениями."""
    fs, project_root = config_fs
    result = cli_runner.invoke(["dev", "setup-github-actions", "--no-interactive"])

    assert result.exit_code == 0
    assert "Workflow успешно сохранен" in result.stdout

    # По умолчанию сохраняется в .github/workflows/ci.yml
    assert fs.exists("src/app/.github/workflows/ci.yml") or fs.exists(".github/workflows/ci.yml")


def test_cli_setup_github_actions_no_interactive_custom(cli_runner, config_fs):
    """Проверяет CLI-команду с флагом --no-interactive и кастомными флагами."""
    fs, project_root = config_fs
    result = cli_runner.invoke([
        "dev", "setup-github-actions", "--no-interactive",
        "--python-versions", "3.11,3.12",
        "--without-pytest",
        "--without-mypy",
        "--output-file", "test_workflow.yml"
    ])

    assert result.exit_code == 0
    assert "Workflow успешно сохранен в test_workflow.yml" in result.stdout
    assert fs.exists("test_workflow.yml")

    with open("test_workflow.yml", "r", encoding="utf-8") as f:
        content = f.read()

    assert 'python-version: ["3.11", "3.12"]' in content
    assert "pytest" not in content
    assert "mypy" not in content
    assert "ruff" in content  # по умолчанию True
    assert "ai-lint" in content  # по умолчанию True


def test_cli_setup_github_actions_empty_python(cli_runner, config_fs):
    """Проверяет ошибку при пустом списке версий Python."""
    result = cli_runner.invoke([
        "dev", "setup-github-actions", "--no-interactive",
        "--python-versions", "  ,  "
    ])

    assert result.exit_code == 1
    assert "Необходимо указать хотя бы одну версию Python" in result.stderr or "Необходимо указать хотя бы одну версию Python" in result.stdout


def test_cli_setup_github_actions_interactive(cli_runner, config_fs, monkeypatch):
    """Проверяет интерактивный режим с вводом пользователя."""
    fs, project_root = config_fs

    inputs = iter([
        "3.12",  # Python versions
        "y",  # with_pytest
        "n",  # with_ruff
        "y",  # with_mypy
        "n",  # with_ai_lint
        "my_ci.yml"  # output file
    ])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(inputs))

    result = cli_runner.invoke(["dev", "setup-github-actions"])

    assert result.exit_code == 0
    assert "Workflow успешно сохранен в my_ci.yml" in result.stdout
    assert fs.exists("my_ci.yml")

    with open("my_ci.yml", "r", encoding="utf-8") as f:
        content = f.read()

    assert 'python-version: ["3.12"]' in content
    assert "pytest" in content
    assert "mypy" in content
    assert "ruff" not in content
    assert "ai-lint" not in content


def test_cli_setup_github_actions_interactive_cancelled(cli_runner, config_fs, monkeypatch):
    """Проверяет отмену интерактивного режима при KeyboardInterrupt."""

    def mock_input(prompt=""):
        raise KeyboardInterrupt()

    monkeypatch.setattr("builtins.input", mock_input)

    result = cli_runner.invoke(["dev", "setup-github-actions"])
    assert result.exit_code == 1
    assert "Настройка отменена пользователем" in result.stdout or "Настройка отменена пользователем" in result.stderr
