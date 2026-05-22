"""
Парсер AST для построения иерархического индекса проекта.
"""

import ast
import re
from pathlib import Path
from typing import List, Union, Dict

from .models import ProjectIndex, Node, Symbol, Breadcrumbs, GraphEdge


class Indexer:
    """Оркестратор индексации проекта."""

    def __init__(self, root_path: str):
        self.root_path = Path(root_path).resolve()
        # Если это пакет (есть __init__), то база для путей - родитель (например, 'src' или корень проекта)
        if (self.root_path / "__init__.py").exists():
            self.project_root = self.root_path.parent
        else:
            self.project_root = self.root_path

        self._graph_map: Dict[str, Dict[str, int]] = {}  # {source: {target: weight}}
        self._public_symbols = self._discover_public_api()

    @property
    def _graph(self) -> List[GraphEdge]:
        """Преобразует внутреннюю карту в список GraphEdge."""
        edges = []
        for source, targets in self._graph_map.items():
            for target, weight in targets.items():
                edges.append(GraphEdge(source=source, target=target, weight=weight))
        return edges

    def _resolve_module_path(self, module_path: str) -> str:
        """Резолвит строку импорта в путь к модулю/пакету внутри проекта."""
        parts = module_path.split('.')
        current = ""
        best_match = ""

        for part in parts:
            if not current:
                current = part
            else:
                current = f"{current}/{part}"

            # Проверяем, существует ли такой путь относительно project_root
            full_path = self.project_root / current
            if full_path.is_dir() or (full_path.with_suffix('.py')).is_file():
                best_match = current

        return best_match if best_match else module_path.replace('.', '/')

    def _record_dependency(self, source: str, target_module: str, force_internal: bool = False):
        """Регистрирует связь между модулями."""
        # Нам нужны только внутренние зависимости chutils или принудительно помеченные
        if not force_internal and not target_module.startswith("chutils") and not target_module.startswith("."):
            return

        # Нормализуем путь цели
        if target_module.startswith(".") and not any(c.isalnum() for c in target_module):
            # Если это чисто точки ('.', '..'), оставляем как есть
            target_path = target_module
        else:
            # Пытаемся зарезолвить в реальный путь модуля
            target_path = self._resolve_module_path(target_module)

        if source == target_path:
            return

        if source not in self._graph_map:
            self._graph_map[source] = {}

        self._graph_map[source][target_path] = self._graph_map[source].get(target_path, 0) + 1

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

    def _get_layer(self, name: str, docstring: str) -> str:
        """Определяет слой абстракции."""
        # 1. Явный оверрайд в docstring
        if "@layer:" in docstring:
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
        # rel_path теперь всегда строится от project_root (например, 'chutils/core')
        rel_path = str(current_path.relative_to(self.project_root)).replace("\\", "/")
        if rel_path.endswith(".py"):
            rel_path = rel_path[:-3]
        if rel_path == ".":
            rel_path = current_path.name

        is_pkg = (current_path / "__init__.py").exists()
        node_type = "package" if is_pkg else "module"

        # Получаем docstring и AST для модуля/пакета
        docstring = ""
        tree = None
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
            layer=self._get_layer(current_path.name.replace(".py", ""), docstring),
            docstring=docstring,
            summary=docstring.split('\n')[0] if docstring else ""
        )

        # Анализ зависимостей
        if tree:
            for item in tree.body:
                if isinstance(item, ast.Import):
                    for alias in item.names:
                        self._record_dependency(rel_path, alias.name)
                elif isinstance(item, ast.ImportFrom):
                    is_relative = item.level > 0
                    base = item.module if item.module else "." * item.level

                    if base:
                        for alias in item.names:
                            if alias.name == "*":
                                self._record_dependency(rel_path, base, force_internal=is_relative)
                                continue

                            if is_relative:
                                # Для относительных импортов в тестах ожидается база ('.', '..')
                                self._record_dependency(rel_path, base, force_internal=True)
                            else:
                                # Для абсолютных строим полный путь 'chutils.core'
                                target = f"{base}.{alias.name}"
                                self._record_dependency(rel_path, target)

        if is_pkg:
            # Обработка пакета
            for item in sorted(current_path.iterdir()):
                if item.is_dir() and not item.name.startswith((".",)) and item.name != "__pycache__":
                    node.children.append(self._build_node_tree(item))
                elif item.suffix == ".py" and item.name != "__init__.py":
                    node.children.append(self._build_node_tree(item))

            # Извлекаем символы из __init__.py (уже распаршен выше)
            if tree:
                node.symbols = self._extract_symbols(tree)
        else:
            # Обработка отдельного модуля
            if tree:
                node.symbols = self._extract_symbols(tree)

        return node

    def _extract_symbols(self, tree: ast.AST) -> List[Symbol]:
        """Извлекает символы из дерева AST."""
        symbols = []
        for top_level in tree.body:
            if isinstance(top_level, (ast.FunctionDef, ast.AsyncFunctionDef)):
                symbols.append(self._build_symbol(top_level, "function"))
            elif isinstance(top_level, ast.ClassDef):
                cls_symbol = self._build_symbol(top_level, "class")
                symbols.append(cls_symbol)
            elif isinstance(top_level, ast.Assign):
                # Простые константы
                for target in top_level.targets:
                    if isinstance(target, ast.Name):
                        symbols.append(Symbol(
                            name=target.id,
                            type="constant",
                            line_number=top_level.lineno,
                            layer=self._get_layer(target.id, "")
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
