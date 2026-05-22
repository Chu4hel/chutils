from chutils.dev.ast_indexer import Indexer


def test_indexer_tree_construction(tmp_path):
    """Тест построения дерева модулей и пакетов."""
    # Создаем временную структуру проекта
    pkg = tmp_path / "my_project"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("VERSION = '1.0'", encoding="utf-8")

    subpkg = pkg / "core"
    subpkg.mkdir()
    (subpkg / "__init__.py").write_text("", encoding="utf-8")
    (subpkg / "utils.py").write_text("def helper(): pass", encoding="utf-8")

    # Индексируем
    indexer = Indexer(str(pkg))
    index = indexer.index()

    # Проверяем результат
    assert index.project_name == "my_project"
    root = index.root
    assert root.type == "package"
    assert len(root.symbols) == 1
    assert root.symbols[0].name == "VERSION"

    assert len(root.children) == 1
    core = root.children[0]
    assert core.name == "core"
    assert core.type == "package"

    assert len(core.children) == 1
    utils = core.children[0]
    assert utils.name == "utils"
    assert utils.type == "module"
    assert len(utils.symbols) == 1
    assert utils.symbols[0].name == "helper"
