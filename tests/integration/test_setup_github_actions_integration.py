from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_cli_setup_github_actions_e2e(tmp_path: Path) -> None:
    """Проверяет сквозной вызов команды через subprocess с записью в файл."""
    output_file = tmp_path / "ci.yml"

    result = subprocess.run(
        [
            sys.executable, "-m", "chutils", "dev", "setup-github-actions",
            "--no-interactive",
            "--python-versions", "3.11,3.12",
            "--without-pytest",
            "--output-file", str(output_file)
        ],
        capture_output=True,
        text=True,
        check=True
    )

    assert result.returncode == 0
    assert "Workflow успешно сохранен" in result.stdout
    assert os.path.exists(output_file)

    with open(output_file, "r", encoding="utf-8") as f:
        content = f.read()

    assert "name: CI" in content
    assert 'python-version: ["3.11", "3.12"]' in content
    assert "uv run pytest" not in content
