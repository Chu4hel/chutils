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


def test_indexer_include_examples(tmp_path):
    """Тест парсинга и включения few-shot примеров."""
    pkg = tmp_path / "project"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")

    # Создаем docs/ai_examples/
    docs_dir = pkg.parent / "docs" / "ai_examples"
    docs_dir.mkdir(parents=True)

    case_dir = docs_dir / "test_case"
    case_dir.mkdir()

    (case_dir / "good_pattern.py").write_text("# Good", encoding="utf-8")
    (case_dir / "bad_pattern.py").write_text("# Bad", encoding="utf-8")
    (case_dir / "README.md").write_text("Description", encoding="utf-8")

    indexer = Indexer(str(pkg))
    index = indexer.index(include_examples=True)

    assert len(index.examples) == 1
    ex = index.examples[0]
    assert ex.name == "test_case"
    assert ex.description == "Description"
    assert ex.good_pattern == "# Good"
    assert ex.bad_pattern == "# Bad"


def test_indexer_gitignore_matching(tmp_path):
    """Тестирует корректность фильтрации путей через GitIgnoreMatcher."""
    from chutils.dev.ast_indexer import GitIgnoreMatcher

    project_dir = tmp_path / "my_project"
    project_dir.mkdir()

    (project_dir / ".gitignore").write_text("""
    # comment
    *.log
    temp/
    /absolute_ignored.py
    """, encoding="utf-8")

    (project_dir / ".chutilsignore").write_text("""
    chutils_ignored.py
    """, encoding="utf-8")

    matcher = GitIgnoreMatcher(project_dir)

    assert matcher.matches("test.log") is True
    assert matcher.matches("src/test.log") is True
    assert matcher.matches("temp/file.py") is True
    assert matcher.matches("src/temp/file.py") is True
    assert matcher.matches("absolute_ignored.py") is True
    assert matcher.matches("src/absolute_ignored.py") is False
    assert matcher.matches("chutils_ignored.py") is True
    assert matcher.matches("src/chutils_ignored.py") is True
    assert matcher.matches("src/app.py") is False


def test_indexer_namespace_directory_traversal(tmp_path):
    """Тестирует обход папок без __init__.py (Namespace Packages)."""
    pkg = tmp_path / "project"
    pkg.mkdir()

    src_dir = pkg / "src"
    src_dir.mkdir()

    core_dir = src_dir / "core"
    core_dir.mkdir()

    (core_dir / "utils.py").write_text("def helper(): pass", encoding="utf-8")
    (core_dir / "ignored.py").write_text("def bad(): pass", encoding="utf-8")
    (pkg / ".gitignore").write_text("ignored.py\n", encoding="utf-8")

    indexer = Indexer(str(pkg))
    index = indexer.index()

    assert index.project_name == "project"

    root = index.root
    assert len(root.children) == 1
    src_node = root.children[0]
    assert src_node.name == "src"
    assert src_node.type == "package"

    assert len(src_node.children) == 1
    core_node = src_node.children[0]
    assert core_node.name == "core"
    assert core_node.type == "package"

    assert len(core_node.children) == 1
    utils_node = core_node.children[0]
    assert utils_node.name == "utils"
    assert utils_node.type == "module"
