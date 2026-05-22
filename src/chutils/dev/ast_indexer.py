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

    def index(self) -> ProjectIndex:
        """Запускает процесс индексации."""
        root_node = self._build_node_tree(self.root_path)
        return ProjectIndex(
            project_name=self.root_path.name,
            root=root_node,
            dependency_graph=self._graph
        )

    def _build_node_tree(self, current_path: Path) -> Node:
        """Рекурсивно строит дерево узлов (пакетов и модулей)."""
        rel_path = str(current_path.relative_to(self.project_root.parent)).replace("\\", "/")

        is_pkg = (current_path / "__init__.py").exists()
        node_type = "package" if is_pkg else "module"

        node = Node(
            name=current_path.name.replace(".py", ""),
            path=rel_path,
            type=node_type
        )

        if is_pkg:
            # Обработка пакета
            for item in sorted(current_path.iterdir()):
                if item.is_dir() and not item.name.startswith(("_", ".")) and item.name != "__pycache__":
                    node.children.append(self._build_node_tree(item))
                elif item.suffix == ".py" and item.name != "__init__.py" and not item.name.startswith("_"):
                    node.children.append(self._build_node_tree(item))

            # Парсим сам __init__.py для символов пакета
            init_file = current_path / "__init__.py"
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
                # Можно добавить методы класса
                symbols.append(cls_symbol)
            elif isinstance(top_level, ast.Assign):
                # Простые константы (только для верхнего уровня)
                for target in top_level.targets:
                    if isinstance(target, ast.Name):
                        symbols.append(Symbol(
                            name=target.id,
                            type="constant",
                            line_number=top_level.lineno
                        ))

        return symbols

    def _build_symbol(self, node: Union[ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef], sym_type: str) -> Symbol:
        """Создает объект Symbol из узла AST."""
        docstring = ast.get_docstring(node) or ""
        summary = docstring.split('\n')[0] if docstring else ""

        breadcrumbs = Breadcrumbs()
        if isinstance(node, ast.AsyncFunctionDef):
            breadcrumbs.is_async = True

        # В следующих фазах добавим более сложный анализ (декораторы, теги)

        return Symbol(
            name=node.name,
            type=sym_type,
            summary=summary,
            docstring=docstring,
            breadcrumbs=breadcrumbs,
            line_number=node.lineno
        )
