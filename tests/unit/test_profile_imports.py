"""
Юнит-тесты для профилировщика импортов chutils dev profile-imports.
"""
from __future__ import annotations

from typing import Any
import json
from unittest.mock import MagicMock

import pytest

from chutils.cli_utils import get_console
from chutils.dev.profile_imports import (
    ImportNode,
    build_tree,
    parse_importtime_line,
    profile_imports,
)


def test_parse_importtime_line() -> None:
    """Проверяет корректность парсинга строк вывода importtime."""
    # Стандартная строка
    node = parse_importtime_line("import time:      150 |          300 |   os")
    assert node is not None
    assert node.name == "os"
    assert node.self_time_ms == 0.15
    assert node.cumulative_time_ms == 0.3
    assert node.depth == 1

    # Вложенная строка
    node = parse_importtime_line("import time:      100 |          100 |     posix")
    assert node is not None
    assert node.name == "posix"
    assert node.self_time_ms == 0.1
    assert node.cumulative_time_ms == 0.1
    assert node.depth == 2

    # Некорректные строки
    assert parse_importtime_line("some random stderr output") is None
    assert parse_importtime_line("import time: invalid") is None


def test_build_tree() -> None:
    """Проверяет правильность построения иерархического дерева из плоского списка."""
    node_c = ImportNode("C", 1.0, 1.0, 2)
    node_b = ImportNode("B", 2.0, 2.0, 2)
    node_a = ImportNode("A", 3.0, 6.0, 1)

    roots = build_tree([node_c, node_b, node_a])
    assert len(roots) == 1
    root = roots[0]
    assert root.name == "A"
    assert len(root.children) == 2
    assert root.children[0].name == "C"
    assert root.children[1].name == "B"


def test_profile_imports_success(mocker: Any, capsys: Any) -> None:
    """Проверяет успешное профилирование и обнаружение тяжелых импортов."""
    mock_run = mocker.patch("subprocess.run")
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.stderr = (
        "import time:      1000 |         1000 |   pydantic\n"
        "import time:      2000 |         3000 | chutils\n"
    )
    mock_run.return_value = mock_proc

    console = get_console()
    profile_imports("chutils", threshold_ms=0.0, as_table=False, as_json=False, console=console)

    captured = capsys.readouterr()
    assert "chutils" in captured.out or "chutils" in captured.err
    # Проверяем предупреждение о тяжелом импорте pydantic
    assert "pydantic" in captured.out


def test_profile_imports_table(mocker: Any, capsys: Any) -> None:
    """Проверяет форматирование вывода в виде таблицы."""
    mock_run = mocker.patch("subprocess.run")
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.stderr = (
        "import time:      1000 |         1000 |   typing\n"
        "import time:      2000 |         3000 | chutils\n"
    )
    mock_run.return_value = mock_proc

    console = get_console()
    profile_imports("chutils", threshold_ms=0.0, as_table=True, as_json=False, console=console)

    captured = capsys.readouterr()
    assert "chutils" in captured.out
    assert "typing" in captured.out


def test_profile_imports_json(mocker: Any, capsys: Any) -> None:
    """Проверяет форматирование вывода в виде JSON."""
    mock_run = mocker.patch("subprocess.run")
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.stderr = (
        "import time:      1000 |         1000 |   typing\n"
        "import time:      2000 |         3000 | chutils\n"
    )
    mock_run.return_value = mock_proc

    console = get_console()
    profile_imports("chutils", threshold_ms=0.0, as_table=False, as_json=True, console=console)

    captured = capsys.readouterr()
    data = json.loads(captured.out.strip())
    assert data["target"] == "chutils"
    assert data["total_imports"] == 2


def test_profile_imports_failure(mocker: Any) -> None:
    """Проверяет генерацию ошибки при сбое подпроцесса."""
    mock_run = mocker.patch("subprocess.run")
    mock_proc = MagicMock()
    mock_proc.returncode = 1
    mock_proc.stderr = "SyntaxError: invalid syntax"
    mock_run.return_value = mock_proc

    console = get_console()
    with pytest.raises(RuntimeError, match="Не удалось импортировать модуль"):
        profile_imports(
            "invalid_target", threshold_ms=0.0, as_table=False, as_json=False, console=console
        )


def test_profile_imports_empty_output(mocker: Any) -> None:
    """Проверяет генерацию ошибки при пустом или некорректном выводе importtime."""
    mock_run = mocker.patch("subprocess.run")
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.stderr = "some non-importtime warning or message"
    mock_run.return_value = mock_proc

    console = get_console()
    with pytest.raises(RuntimeError, match="Не удалось распарсить вывод importtime"):
        profile_imports("chutils", threshold_ms=0.0, as_table=False, as_json=False, console=console)


def test_parse_importtime_value_error() -> None:
    """Проверяет корректное возвращение None при некорректном формате чисел."""
    assert parse_importtime_line("import time:     abc |          123 |   os") is None
    assert parse_importtime_line("import time:     123 |          xyz |   os") is None


def test_profile_imports_many_duplicates(mocker: Any, capsys: Any) -> None:
    """Проверяет вывод предупреждения о дублирующихся импортах, когда их больше 5."""
    mock_run = mocker.patch("subprocess.run")
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    # Генерируем 6 дублирующихся импортов для разных модулей
    mock_proc.stderr = (
        "import time:      1000 |         1000 |   dup1\n"
        "import time:      1000 |         1000 |   dup1\n"
        "import time:      1000 |         1000 |   dup2\n"
        "import time:      1000 |         1000 |   dup2\n"
        "import time:      1000 |         1000 |   dup3\n"
        "import time:      1000 |         1000 |   dup3\n"
        "import time:      1000 |         1000 |   dup4\n"
        "import time:      1000 |         1000 |   dup4\n"
        "import time:      1000 |         1000 |   dup5\n"
        "import time:      1000 |         1000 |   dup5\n"
        "import time:      1000 |         1000 |   dup6\n"
        "import time:      1000 |         1000 |   dup6\n"
        "import time:      2000 |         3000 | chutils\n"
    )
    mock_run.return_value = mock_proc

    console = get_console()
    profile_imports("chutils", threshold_ms=0.0, as_table=False, as_json=False, console=console)

    captured = capsys.readouterr()
    assert "Обнаружены дублирующиеся импорты" in captured.out
    assert "и еще 1 дубликатов" in captured.out


def test_profile_imports_fallback_no_rich(mocker: Any, monkeypatch: Any, capsys: Any) -> None:
    """Проверяет текстовый fallback-рендеринг дерева и таблицы при отсутствии rich."""
    import sys
    for mod_name, mod in list(sys.modules.items()):
        if "chutils.dev.profile_imports" in mod_name and mod:
            monkeypatch.setattr(mod, "RICH_AVAILABLE", False)
            monkeypatch.setattr(mod, "Tree", None)
            monkeypatch.setattr(mod, "Table", None)

    mock_run = mocker.patch("subprocess.run")
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.stderr = (
        "import time:      1000 |         1000 |   typing\n"
        "import time:      2000 |         3000 | chutils\n"
    )
    mock_run.return_value = mock_proc

    console = get_console()

    # 1. Проверяем текстовое дерево
    profile_imports("chutils", threshold_ms=0.0, as_table=False, as_json=False, console=console)
    captured = capsys.readouterr()
    assert "Дерево импортов модулей:" in captured.out
    assert "• typing" in captured.out
    assert "• chutils" in captured.out

    # 2. Проверяем текстовую таблицу
    profile_imports("chutils", threshold_ms=0.0, as_table=True, as_json=False, console=console)
    captured = capsys.readouterr()
    assert "Тяжелые импорты (сортировка по собственному времени):" in captured.out
    assert "typing" in captured.out
    assert "chutils" in captured.out
