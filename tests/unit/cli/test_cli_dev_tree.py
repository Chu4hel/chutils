import json
import sys

import pytest
from chutils.cli import main


def test_cli_generate_context_tree(mocker, capsys):
    """Тест CLI команды с флагом --tree."""
    test_args = ["chutils", "dev", "generate-context", "--tree"]
    mocker.patch.object(sys, 'argv', test_args)

    with pytest.raises(SystemExit) as e:
        main()

    assert e.value.code == 0
    captured = capsys.readouterr()

    # Проверяем, что вывод - валидный JSON с ожидаемыми полями
    data = json.loads(captured.out)
    assert "project_name" in data
    assert "root" in data
    assert "dependency_graph" in data
    assert data["root"]["type"] == "package"


def test_cli_generate_context_tree_no_weights(mocker, capsys):
    """Тест CLI команды с флагами --tree и --no-weights."""
    test_args = ["chutils", "dev", "generate-context", "--tree", "--no-weights"]
    mocker.patch.object(sys, 'argv', test_args)

    with pytest.raises(SystemExit) as e:
        main()

    assert e.value.code == 0
    captured = capsys.readouterr()

    data = json.loads(captured.out)
    # Если в графе есть ребра, их вес должен быть 1
    if data["dependency_graph"]:
        assert all(edge["weight"] == 1 for edge in data["dependency_graph"])
