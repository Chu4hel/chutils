"""Unit-тесты для команды chutils dev lock и дифференциации target в context_metadata.json."""

import json
from pathlib import Path
import pytest

from chutils.dev.project_metadata import save_context_metadata_cache


def test_save_context_metadata_cache_target(tmp_path: Path):
    cache_file = tmp_path / ".chutils" / "context_metadata.json"

    # Сохраняем файл для chutils
    save_context_metadata_cache(
        project_path=tmp_path,
        output_file=str(tmp_path / "api_map.md"),
        format_str="markdown",
        project_hash="hash123",
        target="chutils",
    )

    # Сохраняем файл для проекта
    save_context_metadata_cache(
        project_path=tmp_path,
        output_file=str(tmp_path / "project_index.json"),
        format_str="tree",
        project_hash="hash456",
        target="project",
        tree=True,
    )

    assert cache_file.exists()
    with open(cache_file, encoding="utf-8") as f:
        data = json.load(f)

    files = data.get("files", {})
    assert "api_map.md" in files
    assert files["api_map.md"]["target"] == "chutils"

    assert "project_index.json" in files
    assert files["project_index.json"]["target"] == "project"
    assert files["project_index.json"]["tree"] is True


def test_cli_dev_lock(cli_runner, config_fs, mocker):
    fs, project_root = config_fs

    mocker.patch("os.getcwd", return_value=str(project_root))
    mocker.patch("pathlib.Path.cwd", return_value=project_root)

    # Создаем тестовую запись в реестре .chutils/context_metadata.json
    cache_path = project_root / ".chutils" / "context_metadata.json"
    cache_data = {
        "files": {
            "api_map.md": {
                "format": "markdown",
                "target": "chutils",
                "project_hash": "dummy_hash",
            }
        }
    }
    fs.create_file(cache_path, contents=json.dumps(cache_data))

    result = cli_runner.invoke(["dev", "lock"])
    assert result.exit_code == 0
    assert "Запуск синхронизации и перегенерации" in result.stdout
    assert "api_map.md" in result.stdout
