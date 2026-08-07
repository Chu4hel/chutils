from pathlib import Path
import pytest

from chutils.dev.context import GitIgnoreMatcher, get_changed_files, update_tree_incrementally


def test_gitignore_matcher_basic(tmp_path: Path):
    """Проверяет фильтрацию путей по файлам .gitignore."""
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text("build/\n*.tmp\n!important.tmp\n", encoding="utf-8")

    matcher = GitIgnoreMatcher(tmp_path, use_gitignore=True)

    assert matcher.matches("build/output.py") is True
    assert matcher.matches("test.tmp") is True
    assert matcher.matches("important.tmp") is False
    assert matcher.matches("src/main.py") is False


def test_gitignore_matcher_disabled(tmp_path: Path):
    """Проверяет отключение чтения .gitignore при use_gitignore=False."""
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text("build/\n", encoding="utf-8")

    matcher = GitIgnoreMatcher(tmp_path, use_gitignore=False)

    assert matcher.matches("build/output.py") is False


def test_get_changed_files_empty(tmp_path: Path):
    """Проверяет корректную обработку пути без гита."""
    changed = get_changed_files(tmp_path)
    assert isinstance(changed, list)


def test_update_tree_incrementally_no_changes(tmp_path: Path):
    """Проверяет поведение при отсутствии измененных файлов."""
    old_data = {"root": {"name": "root", "children": []}, "metadata": {"project_hash": "abc"}}
    updated = update_tree_incrementally(
        old_data,
        changed_files=[],
        indexer_class=None,
        project_root=tmp_path,
    )

    assert updated == old_data
