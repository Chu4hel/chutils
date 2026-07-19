from __future__ import annotations

from chutils.dev.github_actions import generate_workflow_yaml


def test_generate_workflow_yaml_default():
    """Проверяет генерацию YAML-файла с дефолтными версиями Python и всеми включенными флагами."""
    python_versions = ["3.10", "3.11", "3.12", "3.13"]
    yaml_content = generate_workflow_yaml(
        python_versions=python_versions,
        with_pytest=True,
        with_mypy=True,
        with_ruff=True,
        with_ai_lint=True,
    )

    assert "name: CI" in yaml_content
    assert 'python-version: ["3.10", "3.11", "3.12", "3.13"]' in yaml_content
    assert "astral-sh/setup-uv" in yaml_content
    assert "uv run ruff check ." in yaml_content
    assert "uv run mypy ." in yaml_content
    assert "uv run chutils dev ai-lint" in yaml_content
    assert "uv run pytest" in yaml_content


def test_generate_workflow_yaml_minimal():
    """Проверяет генерацию YAML-файла без дополнительных инструментов."""
    python_versions = ["3.11"]
    yaml_content = generate_workflow_yaml(
        python_versions=python_versions,
        with_pytest=False,
        with_mypy=False,
        with_ruff=False,
        with_ai_lint=False,
    )

    assert "name: CI" in yaml_content
    assert 'python-version: ["3.11"]' in yaml_content
    assert "astral-sh/setup-uv" in yaml_content
    assert "uv sync" in yaml_content
    assert "ruff" not in yaml_content
    assert "mypy" not in yaml_content
    assert "ai-lint" not in yaml_content
    assert "pytest" not in yaml_content


def test_setup_github_actions_subcommand_methods(monkeypatch):
    """Тестирует внутренние методы класса SetupGithubActionsSubCommand для 100% покрытия."""
    from chutils.commands.dev.setup_github_actions import SetupGithubActionsSubCommand
    import argparse

    cmd = SetupGithubActionsSubCommand()

    # Тест register
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()
    cmd.register(subparsers)
    assert "setup-github-actions" in subparsers.choices

    # Тест _ask_str с вводом
    monkeypatch.setattr("builtins.input", lambda prompt="": "my_val")
    assert cmd._ask_str("Prompt", "default") == "my_val"

    # Тест _ask_str с пустым вводом (дефолт)
    monkeypatch.setattr("builtins.input", lambda prompt="": "")
    assert cmd._ask_str("Prompt", "default") == "default"

    # Тест _ask_yes_no с вводом y/yes
    monkeypatch.setattr("builtins.input", lambda prompt="": "y")
    assert cmd._ask_yes_no("Prompt", False) is True

    # Тест _ask_yes_no с пустым вводом (дефолт)
    monkeypatch.setattr("builtins.input", lambda prompt="": "")
    assert cmd._ask_yes_no("Prompt", True) is True
    assert cmd._ask_yes_no("Prompt", False) is False
