from chutils.dev.version_detector import (
    clean_version_specifier,
    parse_chutils_from_pyproject,
    parse_chutils_from_lockfile,
    parse_chutils_from_requirements,
    parse_version_from_toml,
    parse_version_tuple,
    get_current_version,
    get_git_head_version,
    detect_version_upgrade,
)


def test_clean_version_specifier():
    """Проверяет очистку спецификаторов версий."""
    assert clean_version_specifier("3.2.0") == "3.2.0"
    assert clean_version_specifier("v3.2.0") == "3.2.0"
    assert clean_version_specifier("==3.2.0") == "3.2.0"
    assert clean_version_specifier(">=3.2.0,<4.0.0") == "3.2.0"
    assert clean_version_specifier("^1.5.0") == "1.5.0"
    assert clean_version_specifier("~=2.1.0") == "2.1.0"
    assert clean_version_specifier("chutils (>=3.2.0)") == "3.2.0"
    assert clean_version_specifier(None) is None
    assert clean_version_specifier("") is None


def test_parse_chutils_from_pyproject_chutils_repo():
    """Проверяет извлечение версии самого chutils из pyproject.toml."""
    toml_content = """
[project]
name = "chutils"
version = "3.3.0"
dependencies = []
"""
    assert parse_chutils_from_pyproject(toml_content) == "3.3.0"


def test_parse_chutils_from_pyproject_external_project():
    """Проверяет извлечение версии chutils в стороннем проекте."""
    # PEP 621 dependencies
    toml_pep621 = """
[project]
name = "my_awesome_app"
version = "0.1.0"
dependencies = [
    "chutils (>=3.2.0)",
    "httpx>=0.27.0"
]
"""
    assert parse_chutils_from_pyproject(toml_pep621) == "3.2.0"

    # Poetry dependencies
    toml_poetry = """
[tool.poetry]
name = "my_service"
version = "1.0.0"

[tool.poetry.dependencies]
python = "^3.10"
chutils = "^3.1.5"
"""
    assert parse_chutils_from_pyproject(toml_poetry) == "3.1.5"


def test_parse_chutils_from_lockfile():
    """Проверяет извлечение версии из uv.lock, poetry.lock и Pipfile.lock."""
    uv_lock = """
[[package]]
name = "chutils"
version = "3.2.5"
source = { registry = "https://pypi.org/simple" }

[[package]]
name = "httpx"
version = "0.27.0"
"""
    assert parse_chutils_from_lockfile("uv.lock", uv_lock) == "3.2.5"

    pipfile_lock = """
{
    "default": {
        "chutils": {
            "version": "==3.1.0"
        }
    }
}
"""
    assert parse_chutils_from_lockfile("Pipfile.lock", pipfile_lock) == "3.1.0"


def test_parse_chutils_from_requirements():
    """Проверяет извлечение версии из requirements.txt."""
    req_content = """
# Dependencies
httpx>=0.27.0
chutils==3.3.0
"""
    assert parse_chutils_from_requirements(req_content) == "3.3.0"


def test_parse_version_from_toml():
    """Проверяет корректность парсинга версии из TOML для обратной совместимости."""
    toml_content = """
[project]
name = "chutils"
version = "3.2.0-dev"
dependencies = []
"""
    assert parse_version_from_toml(toml_content) == "3.2.0-dev"

    toml_no_project = """
version = "1.0.0"
"""
    assert parse_version_from_toml(toml_no_project) == "1.0.0"


def test_parse_version_tuple():
    """Проверяет парсинг версии в кортеж."""
    assert parse_version_tuple("3.2.0") == (3, 2, 0)
    assert parse_version_tuple("v1.0.5-dev") == (1, 0, 5)
    assert parse_version_tuple("1.2") == (1, 2)
    assert parse_version_tuple("invalid") == (0,)


def test_get_current_version_with_lockfile(tmp_path, mocker):
    """Проверяет приоритетное извлечение версии из lock-файла стороннего проекта."""
    mocker.patch("importlib.metadata.version", side_effect=Exception("not installed"))
    base_dir = str(tmp_path)

    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nname = "my_app"\nversion = "0.1.0"\ndependencies = ["chutils>=3.0.0"]', encoding="utf-8")

    uv_lock = tmp_path / "uv.lock"
    uv_lock.write_text('[[package]]\nname = "chutils"\nversion = "3.2.1"', encoding="utf-8")

    # Считывается точная версия 3.2.1 из uv.lock, а не версия проекта 0.1.0!
    assert get_current_version(base_dir) == "3.2.1"


def test_get_git_head_version(mocker):
    """Проверяет получение версии Git HEAD с моком subprocess."""
    mock_run = mocker.patch("subprocess.run")

    mock_run.return_value.stdout = '[[package]]\nname = "chutils"\nversion = "2.5.0"'
    mock_run.return_value.returncode = 0
    assert get_git_head_version("/fake/dir") == "2.5.0"

    mock_run.side_effect = Exception("git error")
    assert get_git_head_version("/fake/dir") is None


def test_detect_version_upgrade(mocker):
    """Проверяет логику определения повышения версии."""
    mocker.patch(
        "chutils.dev.version_detector.get_git_head_version",
        side_effect=lambda bd: "3.1.0"
    )

    # 1. Версия повысилась
    mocker.patch(
        "chutils.dev.version_detector.get_current_version",
        side_effect=lambda bd: "3.2.0"
    )
    old, new, upgraded = detect_version_upgrade("/fake/dir")
    assert old == "3.1.0"
    assert new == "3.2.0"
    assert upgraded is True

    # 2. Версия не изменилась
    mocker.patch(
        "chutils.dev.version_detector.get_current_version",
        side_effect=lambda bd: "3.1.0"
    )
    old, new, upgraded = detect_version_upgrade("/fake/dir")
    assert upgraded is False
