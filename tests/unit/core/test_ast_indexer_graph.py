from chutils.dev.ast_indexer import Indexer


def test_dependency_graph_tracking(tmp_path):
    """Тест отслеживания зависимостей между модулями."""
    pkg = tmp_path / "chutils"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("import chutils.core", encoding="utf-8")

    core = pkg / "core.py"
    core.write_text("from . import utils\nfrom chutils.logger import log", encoding="utf-8")

    utils = pkg / "utils.py"
    utils.write_text("import os", encoding="utf-8")  # Внешний импорт, игнорируем

    logger_dir = pkg / "logger"
    logger_dir.mkdir()
    (logger_dir / "__init__.py").write_text("def log(): pass", encoding="utf-8")

    indexer = Indexer(str(pkg))
    index = indexer.index()

    graph = index.dependency_graph

    # Проверяем наличие связей
    # 1. chutils -> chutils/core
    assert any(e.source == "chutils" and e.target == "chutils/core" for e in graph)

    # 2. chutils/core -> . (relative)
    # Примечание: в текущей реализации "." превращается в "."
    assert any(e.source == "chutils/core" and e.target == "." for e in graph)

    # 3. chutils/core -> chutils/logger
    assert any(e.source == "chutils/core" and e.target == "chutils/logger" for e in graph)

    # 4. Внешний импорт 'os' не должен быть в графе
    assert not any(e.target == "os" for e in graph)


def test_dependency_graph_weights(tmp_path):
    """Тест расчета весов связей."""
    pkg = tmp_path / "chutils"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "core.py").write_text("", encoding="utf-8")  # Создаем цель для резолвера

    logic = pkg / "logic.py"
    logic.write_text("import chutils.core\nimport chutils.core\nfrom chutils import core", encoding="utf-8")

    indexer = Indexer(str(pkg))
    index = indexer.index()

    edge = next(e for e in index.dependency_graph if e.source == "chutils/logic" and e.target == "chutils/core")
    assert edge.weight == 3
