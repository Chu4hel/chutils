import os

from chutils.config import _cm, find_project_root
from chutils.config.dev import parse_chutils_ignore, load_ai_lint_config, DEFAULT_AI_LINT_CONFIG


def test_parse_chutils_ignore_not_exists(config_fs):
    """Проверяет, что если файл .chutilsignore отсутствует, возвращается пустой список."""
    fs, project_root = config_fs
    # В config_fs текущая директория - src/app, корень проекта - /home/user/project.
    # get_base_dir() вернет /home/user/project, так как там еще нет pyproject.toml
    # (если мы не используем project_with_marker).
    # Но для parse_chutils_ignore мы явно передаем base_dir.
    res = parse_chutils_ignore(str(project_root))
    assert res == []


def test_parse_chutils_ignore_valid(config_fs):
    """Проверяет корректность парсинга .chutilsignore (комментарии, пустые строки, пробелы)."""
    fs, project_root = config_fs
    ignore_content = """
    # Это комментарий
    .git
    .venv
    
    # Еще комментарий
    *.pyc
    temp/
    """
    fs.create_file(project_root / ".chutilsignore", contents=ignore_content)

    res = parse_chutils_ignore(str(project_root))
    assert res == [".git", ".venv", "*.pyc", "temp/"]


def test_load_ai_lint_config_defaults(project_with_marker):
    """Проверяет загрузку настроек по умолчанию, когда нет других источников."""
    fs, project_root = project_with_marker
    # Сбрасываем пути менеджера, чтобы он нашел наш новый корень с pyproject.toml
    from chutils.config import _cm
    _cm._reset()
    _cm.initialize_paths(find_project_root)

    config = load_ai_lint_config()
    assert config["strict"] is DEFAULT_AI_LINT_CONFIG["strict"]
    assert config["ignore"] == DEFAULT_AI_LINT_CONFIG["ignore"]
    assert config["rules"] == DEFAULT_AI_LINT_CONFIG["rules"]
    assert config["custom_rules_path"] is DEFAULT_AI_LINT_CONFIG["custom_rules_path"]


def test_load_ai_lint_config_pyproject_toml(project_with_marker):
    """Проверяет чтение конфигурации из pyproject.toml."""
    fs, project_root = project_with_marker
    toml_content = """
[tool.chutils.ai-lint]
strict = true
ignore = ["custom_ignore"]
rules = ["RuleA", "RuleB"]
custom_rules_path = "some/path"
"""
    # Пересоздаем pyproject.toml с содержимым
    pyproject_file = project_root / "pyproject.toml"
    if pyproject_file.exists():
        fs.remove(pyproject_file)
    fs.create_file(pyproject_file, contents=toml_content)

    from chutils.config import _cm
    _cm._reset()
    _cm.initialize_paths(find_project_root)

    config = load_ai_lint_config()
    assert config["strict"] is True
    assert config["ignore"] == ["custom_ignore"]
    assert config["rules"] == ["RuleA", "RuleB"]
    assert config["custom_rules_path"] == "some/path"


def test_load_ai_lint_config_config_yml(project_with_marker):
    """Проверяет приоритет config.yml (Dev.AI-Lint) над pyproject.toml."""
    fs, project_root = project_with_marker
    toml_content = """
[tool.chutils.ai-lint]
strict = false
custom_rules_path = "toml_path"
"""
    yml_content = """
Dev:
  AI-Lint:
    strict: true
    custom_rules_path: "yml_path"
"""
    pyproject_file = project_root / "pyproject.toml"
    if pyproject_file.exists():
        fs.remove(pyproject_file)
    fs.create_file(pyproject_file, contents=toml_content)
    fs.create_file(project_root / "config.yml", contents=yml_content)

    from chutils.config import _cm
    _cm._reset()
    _cm.initialize_paths(find_project_root)

    config = load_ai_lint_config()
    assert config["strict"] is True
    assert config["custom_rules_path"] == "yml_path"


def test_load_ai_lint_config_env_vars(project_with_marker):
    """Проверяет приоритет переменных окружения над файлами конфигурации."""
    fs, project_root = project_with_marker
    toml_content = """
[tool.chutils.ai-lint]
strict = false
custom_rules_path = "toml_path"
"""
    pyproject_file = project_root / "pyproject.toml"
    if pyproject_file.exists():
        fs.remove(pyproject_file)
    fs.create_file(pyproject_file, contents=toml_content)

    os.environ["CH_DEV_AILINT_STRICT"] = "true"
    os.environ["CH_DEV_AILINT_CUSTOM_RULES_PATH"] = "env_path"
    os.environ["CH_DEV_AILINT_RULES"] = "[RuleEnv1, RuleEnv2]"

    try:
        from chutils.config import _cm
        _cm._reset()
        _cm.initialize_paths(find_project_root)

        config = load_ai_lint_config()
        assert config["strict"] is True
        assert config["custom_rules_path"] == "env_path"
        assert config["rules"] == ["RuleEnv1", "RuleEnv2"]
    finally:
        del os.environ["CH_DEV_AILINT_STRICT"]
        del os.environ["CH_DEV_AILINT_CUSTOM_RULES_PATH"]
        del os.environ["CH_DEV_AILINT_RULES"]


def test_load_ai_lint_config_cli_args(project_with_marker):
    """Проверяет наивысший приоритет CLI флагов."""
    fs, project_root = project_with_marker
    os.environ["CH_DEV_AILINT_STRICT"] = "false"

    try:
        from chutils.config import _cm
        _cm._reset()
        _cm.initialize_paths(find_project_root)

        cli_args = {
            "strict": True,
            "custom_rules_path": "cli_path"
        }
        config = load_ai_lint_config(cli_args=cli_args)
        assert config["strict"] is True
        assert config["custom_rules_path"] == "cli_path"
    finally:
        del os.environ["CH_DEV_AILINT_STRICT"]


def test_load_ai_lint_config_chutilsignore_merge(project_with_marker):
    """Проверяет слияние .chutilsignore с игнорируемыми путями без дубликатов."""
    fs, project_root = project_with_marker
    toml_content = """
[tool.chutils.ai-lint]
ignore = [".git", "custom_dir"]
"""
    pyproject_file = project_root / "pyproject.toml"
    if pyproject_file.exists():
        fs.remove(pyproject_file)
    fs.create_file(pyproject_file, contents=toml_content)

    ignore_content = """
    custom_dir
    another_dir
    """
    fs.create_file(project_root / ".chutilsignore", contents=ignore_content)

    from chutils.config import _cm
    _cm._reset()
    _cm.initialize_paths(find_project_root)

    config = load_ai_lint_config()
    # .git и custom_dir из pyproject, custom_dir и another_dir из .chutilsignore.
    # custom_dir не должен дублироваться.
    assert sorted(config["ignore"]) == sorted([".git", "custom_dir", "another_dir"])
