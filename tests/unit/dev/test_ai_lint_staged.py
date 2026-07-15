from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Generator

import pytest
from pytest_mock import MockerFixture

from chutils.dev.ai_lint import LinterEngine
from chutils.dev.rules import ManifestRule, EnvSyncRule, APIMapRule


@pytest.fixture
def mock_git_diff(mocker: MockerFixture) -> Generator[mocker.MagicMock, None, None]:
    """Фикстура для мокания вызова git diff."""
    mock_run = mocker.patch("subprocess.run")
    yield mock_run


def test_collect_staged_files_success(mock_git_diff: MockerFixture, tmp_path: Path) -> None:
    """Проверяет успешный сбор staged файлов через git diff."""
    # Настраиваем фейковый вывод git diff
    mock_stdout = "src/chutils/cli.py\ndocs/api_map.md\n"
    mock_git_diff.return_value.stdout = mock_stdout
    mock_git_diff.return_value.returncode = 0

    engine = LinterEngine({"base_dir": str(tmp_path), "staged": True})

    # Создаем временные файлы, чтобы они реально существовали на диске при resolve()
    cli_file = tmp_path / "src/chutils/cli.py"
    cli_file.parent.mkdir(parents=True, exist_ok=True)
    cli_file.touch()

    api_map_file = tmp_path / "docs/api_map.md"
    api_map_file.parent.mkdir(parents=True, exist_ok=True)
    api_map_file.touch()

    files = engine.collect_files()

    assert len(files) == 2
    assert str(cli_file.resolve()) in files
    assert str(api_map_file.resolve()) in files
    mock_git_diff.assert_called_once_with(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=d"],
        cwd=str(tmp_path.resolve()),
        capture_output=True,
        text=True,
        check=True
    )


def test_collect_staged_files_fallback(mock_git_diff: MockerFixture, tmp_path: Path) -> None:
    """Проверяет фолбек на полное сканирование при ошибке git diff."""
    # Настраиваем ошибку git diff
    mock_git_diff.side_effect = subprocess.SubprocessError("Git error")

    # Создаем фейковый файл в директории
    test_file = tmp_path / "test.py"
    test_file.touch()

    engine = LinterEngine({"base_dir": str(tmp_path), "staged": True})
    files = engine.collect_files()

    # Должен сработать fallback и собрать все файлы
    assert len(files) == 1
    assert str(test_file.resolve()) in files


def test_manifest_rule_staged_optimization(tmp_path: Path) -> None:
    """Проверяет оптимизацию ManifestRule в режиме staged."""
    rule = ManifestRule()
    rule.staged = True

    # 1. Если файлы в пакете не менялись, проверка пакета под src/ должна пропускаться
    pkg_dir = tmp_path / "src" / "my_package"
    pkg_dir.mkdir(parents=True, exist_ok=True)
    (pkg_dir / "__init__.py").touch()

    # Передаем пустой список измененных файлов
    results = rule.check(str(tmp_path), [])

    # Ошибка корневого манифеста будет найдена, но ошибки пакета my_package быть не должно,
    # так как в пакете файлы не менялись.
    assert len(results) == 1
    assert "отсутствует корневой" in results[0].message.lower()
    assert not any("my_package" in r.message.lower() for r in results)

    # 2. Если в пакете изменился файл, ManifestRule должен выдать ошибку
    changed_file = str((pkg_dir / "__init__.py").resolve())
    results_with_change = rule.check(str(tmp_path), [changed_file])

    assert len(results_with_change) == 2
    assert any("my_package" in r.message for r in results_with_change)


def test_env_sync_rule_staged_optimization(tmp_path: Path) -> None:
    """Проверяет, что EnvSyncRule пропускает проверку, если env файлы не менялись."""
    rule = EnvSyncRule()
    rule.staged = True

    # Создаем env файлы на диске
    (tmp_path / ".env").touch()

    # Если env файлы не входят в список измененных, проверка пропускается (нет ошибок)
    results = rule.check(str(tmp_path), ["src/cli.py"])
    assert len(results) == 0

    # Если .env входит в список измененных, проверка запускается (найдет расхождение)
    results_with_change = rule.check(str(tmp_path), [str((tmp_path / ".env").resolve())])
    assert len(results_with_change) > 0


def test_api_map_rule_staged_optimization(tmp_path: Path) -> None:
    """Проверяет, что APIMapRule пропускает проверку, если Python-файлы не менялись."""
    rule = APIMapRule()
    rule.staged = True

    # Создаем структуру проекта chutils
    (tmp_path / "src" / "chutils").mkdir(parents=True, exist_ok=True)
    (tmp_path / "api_map.md").touch()

    # Python файлы не менялись (только md) -> проверка пропускается
    results = rule.check(str(tmp_path), ["docs/index.md"])
    assert len(results) == 0

    # Python файл изменился -> проверка запускается (найдет расхождение, так как api_map пустой)
    results_with_change = rule.check(str(tmp_path), ["src/chutils/cli.py"])
    assert len(results_with_change) > 0
