"""Тесты для строгого режима Config API (параметр required)."""
from pathlib import Path

import pytest

from chutils import (
    get_config_value,
    get_config_int,
    get_config_float,
    get_config_boolean,
    get_config_list,
    get_config_section,
    get_config_path,
)
from chutils.config import _cm, find_project_root
from chutils.exceptions import ConfigKeyNotFoundError

FAKE_YAML_CONTENT = """
Database:
  host: localhost
  port: 5432
  timeout: 15.5
  enable_ssl: true
  empty_str: ""
  null_val: null
  empty_list: []
  path_val: "/home/user/project/db.sqlite"

Paths:
  missing_val: null
"""


@pytest.fixture
def initialized_fs(config_fs):
    """Инициализирует фейковую файловую систему с тестовым конфигурационным файлом."""
    fs, project_root = config_fs
    fs.create_file(project_root / "pyproject.toml")
    fs.create_file(project_root / "config.yml", contents=FAKE_YAML_CONTENT)
    _cm.initialize_paths(find_project_root)
    # Принудительно очищаем кэш и перечитываем
    _cm._config_loaded = False
    _cm.config_data = {}
    return fs, project_root


class TestConfigRequired:
    """Тесты на параметр required в getters модуля chutils.config."""

    def test_get_value_success(self, initialized_fs):
        """Проверяет успешное получение существующего значения с required=True."""
        assert get_config_value("Database", "host", required=True) == "localhost"

    def test_get_value_raises_if_missing(self, initialized_fs):
        """Проверяет выброс ConfigKeyNotFoundError, если ключ отсутствует."""
        with pytest.raises(ConfigKeyNotFoundError) as exc_info:
            get_config_value("Database", "missing_key", required=True)
        assert "missing_key" in str(exc_info.value)

    def test_get_value_raises_if_empty_string(self, initialized_fs):
        """Проверяет выброс ConfigKeyNotFoundError, если значение — пустая строка."""
        with pytest.raises(ConfigKeyNotFoundError):
            get_config_value("Database", "empty_str", required=True)

    def test_get_value_raises_if_null(self, initialized_fs):
        """Проверяет выброс ConfigKeyNotFoundError, если значение — null/None."""
        with pytest.raises(ConfigKeyNotFoundError):
            get_config_value("Database", "null_val", required=True)

    def test_get_value_required_false_returns_fallback(self, initialized_fs):
        """Проверяет, что при required=False (или по умолчанию) возвращается fallback."""
        assert get_config_value("Database", "missing_key", fallback="fallback_val") == "fallback_val"
        assert get_config_value("Database", "missing_key") is None
        assert get_config_value("Database", "empty_str", fallback="fallback_val") == "fallback_val"

    # Тесты для get_config_int
    def test_get_int_success(self, initialized_fs):
        assert get_config_int("Database", "port", required=True) == 5432

    def test_get_int_raises_if_missing(self, initialized_fs):
        with pytest.raises(ConfigKeyNotFoundError):
            get_config_int("Database", "missing_port", required=True)

    def test_get_int_required_false(self, initialized_fs):
        assert get_config_int("Database", "missing_port", fallback=999) == 999

    # Тесты для get_config_float
    def test_get_float_success(self, initialized_fs):
        assert get_config_float("Database", "timeout", required=True) == 15.5

    def test_get_float_raises_if_missing(self, initialized_fs):
        with pytest.raises(ConfigKeyNotFoundError):
            get_config_float("Database", "missing_float", required=True)

    def test_get_float_required_false(self, initialized_fs):
        assert get_config_float("Database", "missing_float", fallback=1.23) == 1.23

    # Тесты для get_config_boolean
    def test_get_boolean_success(self, initialized_fs):
        assert get_config_boolean("Database", "enable_ssl", required=True) is True

    def test_get_boolean_raises_if_missing(self, initialized_fs):
        with pytest.raises(ConfigKeyNotFoundError):
            get_config_boolean("Database", "missing_bool", required=True)

    def test_get_boolean_required_false(self, initialized_fs):
        assert get_config_boolean("Database", "missing_bool", fallback=True) is True

    # Тесты для get_config_list
    def test_get_list_success(self, initialized_fs):
        # empty_list в yml парсится как [], что является валидным не-None значением.
        assert get_config_list("Database", "empty_list", required=True) == []

    def test_get_list_raises_if_missing(self, initialized_fs):
        with pytest.raises(ConfigKeyNotFoundError):
            get_config_list("Database", "missing_list", required=True)

    def test_get_list_required_false(self, initialized_fs):
        assert get_config_list("Database", "missing_list", fallback=[1, 2]) == [1, 2]

    # Тесты для get_config_path
    def test_get_path_success(self, initialized_fs):
        val = get_config_path("Database", "path_val", required=True)
        assert Path(val).as_posix().endswith("/home/user/project/db.sqlite")

    def test_get_path_raises_if_missing(self, initialized_fs):
        with pytest.raises(ConfigKeyNotFoundError):
            get_config_path("Database", "missing_path", required=True)

    def test_get_path_required_false(self, initialized_fs):
        assert get_config_path("Database", "missing_path", fallback="fallback", resolve_from_root=False) == "fallback"

    # Тесты для get_config_section
    def test_get_section_success(self, initialized_fs):
        sec = get_config_section("Database", required=True)
        assert isinstance(sec, dict)
        assert sec["host"] == "localhost"

    def test_get_section_raises_if_missing(self, initialized_fs):
        with pytest.raises(ConfigKeyNotFoundError) as exc_info:
            get_config_section("MissingSection", required=True)
        assert "MissingSection" in str(exc_info.value)

    def test_get_section_required_false(self, initialized_fs):
        assert get_config_section("MissingSection", fallback={"ok": 1}) == {"ok": 1}
