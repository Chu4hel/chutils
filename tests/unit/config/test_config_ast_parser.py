from __future__ import annotations

from chutils.config.ast_fallback_parser import (
    parse_fallbacks_from_file,
    parse_fallbacks_from_project,
)


def test_parse_fallbacks_from_file(tmp_path):
    code = """
from chutils import config, get_config_value, get_config_int

# 1. Позиционные аргументы
val1 = get_config_value("Section1", "Key1", "default_val")

# 2. Именованные аргументы
val2 = config.get_config_int(section="Section2", key="Key2", fallback=42)

# 3. Смешанные аргументы (fallback именованный)
val3 = get_config_value("Section3", "Key3", fallback=True)

# 4. Различные типы литералов в fallback
val4 = get_config_value("Section4", "Key4", [1, 2, 3])
val5 = get_config_value("Section4", "Key5", {"a": 1, "b": 2})
val6 = get_config_value("Section4", "Key6", -10.5)

# 5. Игнорирование динамических fallback
dynamic_var = "some_var"
val7 = get_config_value("Section5", "Key7", dynamic_var)
val8 = get_config_value("Section5", "Key8", get_config_int("Sec", "K"))

# 6. Вызов без fallback (не должен ломаться и записываться)
val9 = get_config_value("Section6", "Key9")
"""
    file_path = tmp_path / "test_code.py"
    file_path.write_text(code, encoding="utf-8")

    fallbacks = parse_fallbacks_from_file(str(file_path))

    assert fallbacks["Section1"]["Key1"] == "default_val"
    assert fallbacks["Section2"]["Key2"] == 42
    assert fallbacks["Section3"]["Key3"] is True
    assert fallbacks["Section4"]["Key4"] == [1, 2, 3]
    assert fallbacks["Section4"]["Key5"] == {"a": 1, "b": 2}
    assert fallbacks["Section4"]["Key6"] == -10.5

    # Динамические и без fallback не должны быть извлечены
    assert "Section5" not in fallbacks
    assert "Section6" not in fallbacks


def test_parse_fallbacks_from_project(tmp_path):
    # Создадим структуру папок:
    # app/
    #   main.py (содержит get_config_value)
    #   utils/
    #     helper.py (содержит get_config_int)
    #   tests/
    #     test_main.py (должен игнорироваться)
    #   .venv/
    #     lib.py (должен игнорироваться)

    app_dir = tmp_path / "app"
    app_dir.mkdir()

    utils_dir = app_dir / "utils"
    utils_dir.mkdir()

    tests_dir = app_dir / "tests"
    tests_dir.mkdir()

    venv_dir = app_dir / ".venv"
    venv_dir.mkdir()

    (app_dir / "main.py").write_text(
        'from chutils import get_config_value\n'
        'x = get_config_value("App", "port", 8080)\n',
        encoding="utf-8"
    )

    (utils_dir / "helper.py").write_text(
        'from chutils import get_config_boolean\n'
        'debug = get_config_boolean("App", "debug", True)\n',
        encoding="utf-8"
    )

    (tests_dir / "test_main.py").write_text(
        'from chutils import get_config_value\n'
        '# Должно быть проигнорировано, так как папка tests\n'
        'x = get_config_value("App", "test_key", "ignored_test")\n',
        encoding="utf-8"
    )

    (venv_dir / "lib.py").write_text(
        'from chutils import get_config_value\n'
        '# Должно быть проигнорировано, так как папка .venv\n'
        'x = get_config_value("App", "venv_key", "ignored_venv")\n',
        encoding="utf-8"
    )

    project_fallbacks = parse_fallbacks_from_project(str(app_dir))

    assert project_fallbacks["App"]["port"] == 8080
    assert project_fallbacks["App"]["debug"] is True
    assert "test_key" not in project_fallbacks["App"]
    assert "venv_key" not in project_fallbacks["App"]
