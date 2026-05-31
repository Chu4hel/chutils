from chutils.dev.ast_indexer import Indexer


def test_indexer_deep_features(tmp_path):
    """Тест глубокой индексации: наследование, методы, абстрактные методы."""
    pkg = tmp_path / "deep_project"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")

    code = """
from abc import ABC, abstractmethod
from pydantic import BaseModel

class Base(ABC):
    @abstractmethod
    def run(self):
        \"\"\"Abstract run.\"\"\"
        pass

class MyModel(BaseModel, Base):
    def __init__(self, x):
        self.x = x
        
    def save(self):
        \"\"\"Save data.\"\"\"
        pass
        
    def __private(self):
        pass
"""
    (pkg / "models.py").write_text(code, encoding="utf-8")

    indexer = Indexer(str(pkg))
    index = indexer.index()

    models_node = index.root.children[0]
    symbols = {s.name: s for s in models_node.symbols}

    # 1. Проверка наследования
    base_cls = symbols["Base"]
    assert base_cls.bases == ["abc.ABC"]

    model_cls = symbols["MyModel"]
    assert "pydantic.BaseModel" in model_cls.bases
    assert "Base" in model_cls.bases

    # 2. Проверка методов
    assert len(model_cls.children) == 2
    methods = {m.name: m for m in model_cls.children}
    assert "__init__" in methods
    assert "save" in methods
    assert "__private" not in methods  # Должен быть отфильтрован как dunder

    # 3. Проверка абстрактных методов
    assert len(base_cls.children) == 1
    run_method = base_cls.children[0]
    assert run_method.name == "run"
    assert run_method.breadcrumbs.is_abstract is True


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
