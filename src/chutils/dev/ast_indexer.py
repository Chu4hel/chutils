"""
Парсер AST для построения иерархического индекса проекта.
"""

import ast
from pathlib import Path
from typing import List, Union

from .models import ProjectIndex, Node, Symbol, Breadcrumbs, GraphEdge


class Indexer:
    """Оркестратор индексации проекта."""

    def __init__(self, root_path: str):
        self.root_path = Path(root_path).resolve()
        self.project_root = self.root_path.parent if (self.root_path / "__init__.py").exists() else self.root_path
        self._graph: List[GraphEdge] = []
        self._public_symbols = self._discover_public_api()

    def _discover_public_api(self) -> set:
        """Парсит основной __init__.py для поиска публичных экспортов."""
        init_file = self.root_path / "__init__.py"
        if not init_file.exists():
            return set()

        try:
            tree = ast.parse(init_file.read_text(encoding="utf-8"))
            # Ищем _LAZY_MAPPING или __all__
            public = set()
            for node in tree.body:
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id in ("_LAZY_MAPPING", "__all__"):
                            if isinstance(node.value, ast.Dict):
                                # Случай с _LAZY_MAPPING
                                for k in node.value.keys:
                                    if isinstance(k, ast.Constant):
                                        public.add(k.value)
                            elif isinstance(node.value, (ast.List, ast.Tuple)):
                                # Случай с __all__
                                for elt in node.value.elts:
                                    if isinstance(elt, ast.Constant):
                                        public.add(elt.value)
            return public
        except Exception:
            return set()

    def index(self) -> ProjectIndex:
        """Запускает процесс индексации."""
        root_node = self._build_node_tree(self.root_path)
        return ProjectIndex(
            project_name=self.root_path.name,
            root=root_node,
            dependency_graph=self._graph
        )

    def _get_layer(self, name: str, docstring: str, is_module: bool = False) -> str:
        """Определяет слой абстракции."""
        # 1. Явный оверрайд в docstring
        if "@layer:" in docstring:
            import re
            match = re.search(r"@layer:\s*(\w+)", docstring)
            if match:
                return match.group(1).lower()

        # 2. Приватные символы
        if name.startswith("_"):
            return "private"

        # 3. Публичное API
        if name in self._public_symbols:
            return "public"

        return "internal"

    def _build_node_tree(self, current_path: Path) -> Node:
        """Рекурсивно строит дерево узлов (пакетов и модулей)."""
        rel_path = str(current_path.relative_to(self.project_root.parent)).replace("\\", "/")

        is_pkg = (current_path / "__init__.py").exists()
        node_type = "package" if is_pkg else "module"

        # Получаем docstring для модуля/пакета
        docstring = ""
        init_file = current_path / "__init__.py" if is_pkg else current_path
        if init_file.exists():
            try:
                tree = ast.parse(init_file.read_text(encoding="utf-8"))
                docstring = ast.get_docstring(tree) or ""
            except Exception:
                pass

        node = Node(
            name=current_path.name.replace(".py", ""),
            path=rel_path,
            type=node_type,
            layer=self._get_layer(current_path.name.replace(".py", ""), docstring, True),
            docstring=docstring,
            summary=docstring.split('\n')[0] if docstring else ""
        )

        if is_pkg:
            # Обработка пакета
            for item in sorted(current_path.iterdir()):
                if item.is_dir() and not item.name.startswith((".",)) and item.name != "__pycache__":
                    # Мы не пропускаем папки начинающиеся с _, но помечаем их как private
                    node.children.append(self._build_node_tree(item))
                elif item.suffix == ".py" and item.name != "__init__.py":
                    node.children.append(self._build_node_tree(item))

            # Парсим сам __init__.py для символов пакета
            if init_file.exists():
                node.symbols = self._parse_file_symbols(init_file)
        else:
            # Обработка отдельного модуля
            node.symbols = self._parse_file_symbols(current_path)

        return node

    def _parse_file_symbols(self, file_path: Path) -> List[Symbol]:
        """Извлекает символы из файла через AST."""
        try:
            tree = ast.parse(file_path.read_text(encoding="utf-8"))
        except Exception:
            return []

        symbols = []
        for top_level in tree.body:
            if isinstance(top_level, (ast.FunctionDef, ast.AsyncFunctionDef)):
                symbols.append(self._build_symbol(top_level, "function"))
            elif isinstance(top_level, ast.ClassDef):
                cls_symbol = self._build_symbol(top_level, "class")
                symbols.append(cls_symbol)
            elif isinstance(top_level, ast.Assign):
                # Простые константы (только для верхнего уровня)
                for target in top_level.targets:
                    if isinstance(target, ast.Name):
                        doc = ""  # У констант в ast нет докстрингов напрямую ниже
                        symbols.append(Symbol(
                            name=target.id,
                            type="constant",
                            line_number=top_level.lineno,
                            layer=self._get_layer(target.id, doc)
                        ))

        return symbols

    def _build_symbol(self, node: Union[ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef], sym_type: str) -> Symbol:
        """Создает объект Symbol из узла AST."""
        docstring = ast.get_docstring(node) or ""
        summary = docstring.split('\n')[0] if docstring else ""

        # Извлекаем сигнатуру
        signature = ""
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            try:
                # Очень упрощенная сборка сигнатуры из AST
                args = []
                for arg in node.args.args:
                    args.append(arg.arg)
                signature = f"({', '.join(args)})"
            except Exception:
                signature = "(...)"

        # Собираем хлебные крошки
        breadcrumbs = Breadcrumbs()
        if isinstance(node, ast.AsyncFunctionDef):
            breadcrumbs.is_async = True

        # Декораторы
        for dec in node.decorator_list:
            if isinstance(dec, ast.Name):
                breadcrumbs.decorators.append(dec.id)
            elif isinstance(dec, ast.Attribute) and isinstance(dec.value, ast.Name):
                breadcrumbs.decorators.append(f"{dec.value.id}.{dec.attr}")
            elif isinstance(dec, ast.Call):
                if isinstance(dec.func, ast.Name):
                    breadcrumbs.decorators.append(dec.func.id)
                elif isinstance(dec.func, ast.Attribute) and isinstance(dec.func.value, ast.Name):
                    breadcrumbs.decorators.append(f"{dec.func.value.id}.{dec.func.attr}")

        # Теги из docstring (:tag:)
        import re
        tags = re.findall(r":([\w-]+):", docstring)
        breadcrumbs.tags = list(set(tags))

        if "thread-safe" in breadcrumbs.tags:
            breadcrumbs.is_thread_safe = True
        if "heavy" in breadcrumbs.tags:
            breadcrumbs.is_heavy = True

        return Symbol(
            name=node.name,
            type=sym_type,
            signature=signature,
            summary=summary,
            docstring=docstring,
            breadcrumbs=breadcrumbs,
            line_number=node.lineno,
            layer=self._get_layer(node.name, docstring)
        )
