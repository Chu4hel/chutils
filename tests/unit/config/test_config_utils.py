from chutils.config.utils import deep_merge


def test_deep_merge_basic():
    dict1 = {"a": 1, "b": {"c": 2}}
    dict2 = {"b": {"d": 3}, "e": 4}
    expected = {"a": 1, "b": {"c": 2, "d": 3}, "e": 4}

    result = deep_merge(dict1, dict2)
    assert result == expected
    # Проверка изменения на месте
    assert dict1 == expected


def test_deep_merge_overwrite():
    dict1 = {"a": 1, "b": {"c": 2}}
    dict2 = {"a": 10, "b": {"c": 20}}
    expected = {"a": 10, "b": {"c": 20}}

    result = deep_merge(dict1, dict2)
    assert result == expected


def test_deep_merge_mixed_types():
    dict1 = {"a": {"b": 1}}
    dict2 = {"a": 2}
    expected = {"a": 2}

    result = deep_merge(dict1, dict2)
    assert result == expected


def test_deep_merge_empty():
    dict1 = {"a": 1}
    dict2 = {}
    assert deep_merge(dict1, dict2) == {"a": 1}

    dict1 = {}
    dict2 = {"a": 1}
    assert deep_merge(dict1, dict2) == {"a": 1}


def test_find_project_root_pyproject_and_git(tmp_path):
    from chutils.config.utils import find_project_root
    from chutils.config.manager import _ConfigManager

    # Создаем структуру: root/.git, root/sub/nested
    root_dir = tmp_path / "project_root"
    nested_dir = root_dir / "sub" / "nested"
    nested_dir.mkdir(parents=True)

    git_dir = root_dir / ".git"
    git_dir.mkdir()

    found = find_project_root(nested_dir, _ConfigManager.CONFIG_MARKERS)
    assert found == root_dir


def test_find_project_root_ai_manifest(tmp_path):
    from chutils.config.utils import find_project_root
    from chutils.config.manager import _ConfigManager

    root_dir = tmp_path / "manifest_root"
    nested_dir = root_dir / "src" / "pkg"
    nested_dir.mkdir(parents=True)

    manifest_file = root_dir / "GEMINI.md"
    manifest_file.write_text("# AI Manifest")

    found = find_project_root(nested_dir, _ConfigManager.FALLBACK_MARKERS)
    assert found == root_dir


def test_primary_markers_take_priority_over_fallback(tmp_path):
    from chutils.config.utils import find_project_root
    from chutils.config.manager import _ConfigManager

    # Корень проекта имеет pyproject.toml
    root_dir = tmp_path / "root"
    sub_dir = root_dir / "backend"
    sub_dir.mkdir(parents=True)

    (root_dir / "pyproject.toml").write_text("[project]\nname='root'")
    (sub_dir / "GEMINI.md").write_text("# Local manifest")

    # Первичный поиск по CONFIG_MARKERS должен найти root_dir (pyproject.toml), а не остановиться на sub_dir (GEMINI.md)
    found_primary = find_project_root(sub_dir, _ConfigManager.CONFIG_MARKERS)
    assert found_primary == root_dir


