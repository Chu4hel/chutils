from chutils.dev.ast_indexer import Indexer


def test_layer_identification_public(tmp_path):
    """Тест определения публичного слоя через __init__.py."""
    pkg = tmp_path / "chutils"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("_LAZY_MAPPING = {'get_config': ('.core', None)}", encoding="utf-8")

    module = pkg / "core.py"
    module.write_text("def get_config(): pass", encoding="utf-8")

    indexer = Indexer(str(pkg))
    index = indexer.index()

    # Ищем символ в дереве
    core_node = next(c for c in index.root.children if c.name == "core")
    symbol = next(s for s in core_node.symbols if s.name == "get_config")

    assert symbol.layer == "public"


def test_layer_identification_private(tmp_path):
    """Тест определения приватного слоя через префикс подчеркивания."""
    pkg = tmp_path / "chutils"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")

    module = pkg / "_internal.py"
    module.write_text("def _hidden(): pass", encoding="utf-8")

    indexer = Indexer(str(pkg))
    index = indexer.index()

    internal_node = next(c for c in index.root.children if c.name == "_internal")
    assert internal_node.layer == "private"

    symbol = internal_node.symbols[0]
    assert symbol.name == "_hidden"
    assert symbol.layer == "private"


def test_layer_identification_override(tmp_path):
    """Тест переопределения слоя через @layer в docstring."""
    pkg = tmp_path / "chutils"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")

    module = pkg / "infra.py"
    module.write_text('"""\n@layer: infrastructure\n"""\ndef setup():\n    """@layer: setup"""\n    pass',
                      encoding="utf-8")

    indexer = Indexer(str(pkg))
    index = indexer.index()

    infra_node = next(c for c in index.root.children if c.name == "infra")
    assert infra_node.layer == "infrastructure"

    symbol = infra_node.symbols[0]
    assert symbol.layer == "setup"


def test_layer_identification_internal(tmp_path):
    """Тест слоя по умолчанию (internal)."""
    pkg = tmp_path / "chutils"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")

    module = pkg / "logic.py"
    module.write_text("def process(): pass", encoding="utf-8")

    indexer = Indexer(str(pkg))
    index = indexer.index()

    logic_node = next(c for c in index.root.children if c.name == "logic")
    assert logic_node.layer == "internal"

    symbol = logic_node.symbols[0]
    assert symbol.layer == "internal"
