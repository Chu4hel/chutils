from chutils.dev.ast_indexer import Indexer


def test_metadata_extraction_async_and_tags(tmp_path):
    """Тест извлечения async и тегов из docstring."""
    pkg = tmp_path / "chutils"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")

    module = pkg / "worker.py"
    content = '''
async def process_data(data):
    """
    Выполняет тяжелую задачу.
    :heavy: :thread-safe:
    """
    pass
'''
    module.write_text(content, encoding="utf-8")

    indexer = Indexer(str(pkg))
    index = indexer.index()

    worker_node = next(c for c in index.root.children if c.name == "worker")
    symbol = worker_node.symbols[0]

    assert symbol.name == "process_data"
    assert symbol.breadcrumbs.is_async is True
    assert symbol.breadcrumbs.is_heavy is True
    assert symbol.breadcrumbs.is_thread_safe is True
    assert "heavy" in symbol.breadcrumbs.tags
    assert "thread-safe" in symbol.breadcrumbs.tags
    assert symbol.signature == "(data)"


def test_metadata_extraction_decorators(tmp_path):
    """Тест извлечения декораторов."""
    pkg = tmp_path / "chutils"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")

    module = pkg / "api.py"
    content = '''
@retry(retries=3)
@app.route("/")
def get_root():
    pass
'''
    module.write_text(content, encoding="utf-8")

    indexer = Indexer(str(pkg))
    index = indexer.index()

    api_node = next(c for c in index.root.children if c.name == "api")
    symbol = api_node.symbols[0]

    assert "retry" in symbol.breadcrumbs.decorators
    assert "app.route" in symbol.breadcrumbs.decorators
