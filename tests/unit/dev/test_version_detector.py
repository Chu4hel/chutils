from chutils.dev.version_detector import (
    parse_version_from_toml,
    parse_version_tuple,
    get_current_version,
    get_git_head_version,
    detect_version_upgrade,
)


def test_parse_version_from_toml():
    """Проверяет корректность парсинга версии из TOML."""
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

    toml_invalid = "name = 'test'"
    assert parse_version_from_toml(toml_invalid) is None


def test_parse_version_tuple():
    """Проверяет парсинг версии в кортеж."""
    assert parse_version_tuple("3.2.0") == (3, 2, 0)
    assert parse_version_tuple("v1.0.5-dev") == (1, 0, 5)
    assert parse_version_tuple("1.2") == (1, 2)
    assert parse_version_tuple("invalid") == (0,)


def test_get_current_version(tmp_path):
    """Проверяет чтение текущей версии из файла."""
    base_dir = str(tmp_path)
    # Файла нет
    assert get_current_version(base_dir) is None

    # Файл есть
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nversion = "2.5.1"', encoding="utf-8")
    assert get_current_version(base_dir) == "2.5.1"


def test_get_git_head_version(mocker):
    """Проверяет получение версии Git HEAD с моком subprocess."""
    mock_run = mocker.patch("subprocess.run")

    # Успешный запуск
    mock_run.return_value.stdout = '[project]\nversion = "2.5.0"'
    mock_run.return_value.returncode = 0
    assert get_git_head_version("/fake/dir") == "2.5.0"

    # Ошибка запуска
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

    # 3. Версия понизилась (не апгрейд)
    mocker.patch(
        "chutils.dev.version_detector.get_current_version",
        side_effect=lambda bd: "3.0.0"
    )
    old, new, upgraded = detect_version_upgrade("/fake/dir")
    assert upgraded is False

    # 4. Ошибка чтения одной из версий
    mocker.patch(
        "chutils.dev.version_detector.get_current_version",
        side_effect=lambda bd: None
    )
    old, new, upgraded = detect_version_upgrade("/fake/dir")
    assert upgraded is False
