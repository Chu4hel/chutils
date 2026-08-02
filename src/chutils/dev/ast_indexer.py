# ruff: noqa: E402
"""
Парсер AST для построения иерархического индекса проекта.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from .models import ProjectIndex, Node, Symbol, Breadcrumbs, GraphEdge, ProjectExample


class GitIgnoreMatcher:
    """Проверяет соответствие путей правилам .gitignore, .chutilsignore и пользовательским флагам."""

    def __init__(self, root_path: Path, custom_ignore: list[str] | None = None) -> None:
        """Инициализирует GitIgnoreMatcher.

        Args:
            root_path: Корневой путь проекта.
            custom_ignore: Дополнительные паттерны для игнорирования.
        """
        self.root_path = root_path
        self.patterns: list[tuple[re.Pattern[str], bool]] = []
        self._load_file_rules(self.root_path / ".gitignore")
        self._load_file_rules(self.root_path / ".chutilsignore")
        if custom_ignore:
            for rule in custom_ignore:
                rule_str = rule.strip()
                if not rule_str or rule_str.startswith("#"):
                    continue
                is_negative = False
                if rule_str.startswith("!"):
                    is_negative = True
                    rule_str = rule_str[1:]
                regex = self._rule_to_regex(rule_str)
                if regex:
                    self.patterns.append((regex, is_negative))

    def _load_file_rules(self, file_path: Path) -> None:
        if not file_path.exists():
            return

        try:
            lines = file_path.read_text(encoding="utf-8").splitlines()
            for line in lines:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                is_negative = False
                if line.startswith("!"):
                    is_negative = True
                    line = line[1:]

                regex = self._rule_to_regex(line)
                if regex:
                    self.patterns.append((regex, is_negative))
        except Exception:
            pass

    def _rule_to_regex(self, rule: str) -> re.Pattern[str] | None:
        rule = rule.replace("\\", "/")
        if not rule:
            return None

        # Определяем, привязано ли правило к корню
        stripped_rule = rule[:-1] if rule.endswith("/") else rule
        anchored = "/" in stripped_rule or rule.startswith("/")

        if rule.startswith("/"):
            rule = rule[1:]

        parts = []
        i = 0
        n = len(rule)
        while i < n:
            c = rule[i]
            if c == '*':
                if i + 1 < n and rule[i + 1] == '*':
                    parts.append('__DOUBLE_STAR__')
                    i += 2
                else:
                    parts.append('__STAR__')
                    i += 1
            elif c == '?':
                parts.append('[^/]')
                i += 1
            elif c in ('.', '+', '^', '$', '(', ')', '{', '}', '|', '\\'):
                parts.append('\\' + c)
                i += 1
            else:
                parts.append(c)
                i += 1

        regex_str = "".join(parts)
        regex_str = regex_str.replace('__DOUBLE_STAR__', '.*')
        regex_str = regex_str.replace('__STAR__', '[^/]*')

        if rule.endswith("/"):
            regex_str += '?.*'
        else:
            regex_str += '(/.*)?$'

        if anchored:
            regex_str = '^' + regex_str
        else:
            regex_str = '(^|.*/)' + regex_str

        try:
            return re.compile(regex_str)
        except re.error:
            return None

    def matches(self, rel_path: str) -> bool:
        """Возвращает True, если путь должен быть проигнорирован.

        Args:
            rel_path: Относительный путь для проверки.

        Returns:
            True, если путь игнорируется, иначе False.
        """
        rel_path = rel_path.replace("\\", "/").lstrip("/")
        if not rel_path:
            return False

        is_ignored = False
        for pattern, is_negative in self.patterns:
            if pattern.search(rel_path):
                is_ignored = not is_negative
        return is_ignored


class Indexer:
    """Оркестратор индексации проекта."""

    def __init__(self, root_path: str, custom_ignore: list[str] | None = None) -> None:
        """Инициализирует Indexer.

        Args:
            root_path: Корневой путь к исходному коду проекта.
            custom_ignore: Список дополнительных паттернов для игнорирования.
        """
        self.root_path = Path(root_path).resolve()
        # Если это пакет (есть __init__), то база для путей - родитель (например, 'src' или корень проекта)
        if (self.root_path / "__init__.py").exists():
            self.project_root = self.root_path.parent
        else:
            self.project_root = self.root_path

        self._graph_map: dict[str, dict[str, int]] = {}  # {source: {target: weight}}
        self._current_imports: dict[str, str] = {}
        """Карта импортов текущего модуля {asname: full_path}"""
        self._public_symbols = self._discover_public_api()
        self.gitignore = GitIgnoreMatcher(self.project_root, custom_ignore=custom_ignore)

    @property
    def _graph(self) -> list[GraphEdge]:
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

    def _record_dependency(self, source: str, target_module: str, force_internal: bool = False) -> None:
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

    def _discover_public_api(self) -> set[str]:
        """Парсит основной __init__.py для поиска публичных экспортов."""
        init_file = self.root_path / "__init__.py"
        if not init_file.exists():
            return set()

        try:
            tree = ast.parse(init_file.read_text(encoding="utf-8"))
            # Ищем _LAZY_MAPPING или __all__
            public: set[str] = set()
            for node in tree.body:
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id in ("_LAZY_MAPPING", "__all__"):
                            if isinstance(node.value, ast.Dict):
                                # Случай с _LAZY_MAPPING
                                for k in node.value.keys:
                                    if k is not None and isinstance(k, ast.Constant):
                                        public.add(str(k.value))
                            elif isinstance(node.value, (ast.List, ast.Tuple)):
                                # Случай с __all__
                                for elt in node.value.elts:
                                    if isinstance(elt, ast.Constant):
                                        public.add(str(elt.value))
            return public
        except Exception:
            return set()

    def _collect_examples(self) -> list[ProjectExample]:
        """Служит для сбора few-shot примеров из папки docs/ai_examples/."""
        examples: list[ProjectExample] = []

        examples_dir = None
        if (self.project_root / "docs" / "ai_examples").exists():
            examples_dir = self.project_root / "docs" / "ai_examples"
        elif (self.project_root.parent / "docs" / "ai_examples").exists():
            examples_dir = self.project_root.parent / "docs" / "ai_examples"

        if not examples_dir or not examples_dir.exists():
            return examples

        for item in sorted(examples_dir.iterdir()):
            if item.is_dir() and not item.name.startswith("."):
                good_path = item / "good_pattern.py"
                bad_path = item / "bad_pattern.py"
                readme_path = item / "README.md"

                good_code = good_path.read_text(encoding="utf-8") if good_path.exists() else ""
                bad_code = bad_path.read_text(encoding="utf-8") if bad_path.exists() else ""
                readme_text = readme_path.read_text(encoding="utf-8") if readme_path.exists() else ""

                if good_code or bad_code or readme_text:
                    examples.append(ProjectExample(
                        name=item.name,
                        description=readme_text,
                        good_pattern=good_code,
                        bad_pattern=bad_code
                    ))
        return examples

    def index(self, include_examples: bool = False) -> ProjectIndex:
        """Запускает процесс индексации.

        Args:
            include_examples: Флаг включения примеров кода в индекс.

        Returns:
            Объект ProjectIndex с результатами индексации.
        """
        root_node = self._build_node_tree(self.root_path)
        examples = self._collect_examples() if include_examples else []
        metadata = collect_project_metadata(self.project_root)
        return ProjectIndex(
            project_name=self.root_path.name,
            root=root_node,
            dependency_graph=self._graph,
            examples=examples,
            metadata=metadata
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

        is_dir = current_path.is_dir()
        is_pkg = is_dir and (current_path / "__init__.py").exists()
        node_type = "package" if is_dir else "module"

        # Получаем docstring и AST для модуля/пакета
        docstring = ""
        tree: ast.Module | None = None
        init_file = current_path / "__init__.py" if is_pkg else (None if is_dir else current_path)
        if init_file and init_file.exists():
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
        self._current_imports = {}
        if tree:
            for item in tree.body:
                if isinstance(item, ast.Import):
                    for alias in item.names:
                        self._record_dependency(rel_path, alias.name)
                        self._current_imports[alias.asname or alias.name] = alias.name
                elif isinstance(item, ast.ImportFrom):
                    is_relative = item.level is not None and item.level > 0
                    level = item.level if item.level is not None else 0
                    prefix = "." * level
                    base_mod = item.module if item.module else ""
                    full_base = prefix + base_mod

                    if full_base:
                        for alias in item.names:
                            if alias.name == "*":
                                self._record_dependency(rel_path, full_base, force_internal=is_relative)
                                continue

                            # Формируем полное имя: .base.ClassName или ClassName
                            if base_mod:
                                full_name = f"{full_base}.{alias.name}"
                            else:
                                full_name = f"{full_base}{alias.name}"

                            self._current_imports[alias.asname or alias.name] = full_name

                            if is_relative:
                                # Для относительных импортов регистрируем зависимость
                                self._record_dependency(rel_path, full_base, force_internal=True)
                            else:
                                self._record_dependency(rel_path, full_name)

        if is_dir:
            # Обработка пакета или директории
            for fs_item in sorted(current_path.iterdir()):
                # Проверяем .gitignore целевого проекта
                rel_item_path = str(fs_item.relative_to(self.project_root)).replace("\\", "/")
                if self.gitignore.matches(rel_item_path):
                    continue

                if fs_item.is_dir():
                    # Пропускаем скрытые папки (начинающиеся с .) и __pycache__
                    if fs_item.name.startswith(".") or fs_item.name == "__pycache__":
                        continue
                    node.children.append(self._build_node_tree(fs_item))
                elif fs_item.suffix == ".py" and fs_item.name != "__init__.py":
                    node.children.append(self._build_node_tree(fs_item))

            # Извлекаем символы из __init__.py (уже распаршен выше)
            if is_pkg and tree:
                node.symbols = self._extract_symbols(tree)
        else:
            # Обработка отдельного модуля
            if tree:
                node.symbols = self._extract_symbols(tree)

        return node

    def _extract_symbols(self, tree: ast.Module) -> list[Symbol]:
        """Извлекает символы из дерева AST."""
        symbols: list[Symbol] = []
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
                        if target.id.startswith("__") and target.id.endswith("__"):
                            continue
                        symbols.append(Symbol(
                            name=target.id,
                            type="constant",
                            line_number=top_level.lineno,
                            layer=self._get_layer(target.id, "")
                        ))
        return symbols

    def _resolve_base_class(self, base_name: str) -> str:
        """Разрешает имя базового класса в полный путь импорта."""
        return self._current_imports.get(base_name, base_name)

    def _build_symbol(self, node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef, sym_type: str) -> Symbol:
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
            dec_name = ""
            if isinstance(dec, ast.Name):
                dec_name = dec.id
            elif isinstance(dec, ast.Attribute) and isinstance(dec.value, ast.Name):
                dec_name = f"{dec.value.id}.{dec.attr}"
            elif isinstance(dec, ast.Call):
                if isinstance(dec.func, ast.Name):
                    dec_name = dec.func.id
                elif isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute) and isinstance(dec.func.value,
                                                                                                      ast.Name):
                    dec_name = f"{dec.func.value.id}.{dec.func.attr}"

            if dec_name:
                breadcrumbs.decorators.append(dec_name)
                if dec_name == "abstractmethod" or dec_name.endswith(".abstractmethod"):
                    breadcrumbs.is_abstract = True

        # Теги из docstring (:tag:)
        tags = re.findall(r":([\w-]+):", docstring)
        breadcrumbs.tags = sorted(list(set(tags)))

        if "thread-safe" in breadcrumbs.tags:
            breadcrumbs.is_thread_safe = True
        if "heavy" in breadcrumbs.tags:
            breadcrumbs.is_heavy = True

        symbol = Symbol(
            name=node.name,
            type=sym_type,
            signature=signature,
            summary=summary,
            docstring=docstring,
            breadcrumbs=breadcrumbs,
            line_number=node.lineno,
            layer=self._get_layer(node.name, docstring)
        )

        if isinstance(node, ast.ClassDef):
            # Извлекаем базы
            for base in node.bases:
                base_path = ""
                if isinstance(base, ast.Name):
                    base_path = self._resolve_base_class(base.id)
                elif isinstance(base, ast.Attribute):
                    # Случай типа pydantic.BaseModel
                    parts: list[str] = []
                    curr: ast.AST = base
                    while isinstance(curr, ast.Attribute):
                        parts.append(curr.attr)
                        curr = curr.value
                    if isinstance(curr, ast.Name):
                        parts.append(curr.id)
                    base_path = ".".join(reversed(parts))

                if base_path:
                    symbol.bases.append(base_path)
                    # Если наследуется от ABC, помечаем класс как абстрактный
                    if base_path in ("ABC", "abc.ABC", "abc.ABCMeta"):
                        symbol.breadcrumbs.is_abstract = True

            # Извлекаем методы
            has_abstract_methods = False
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    # Фильтрация: оставляем публичные, защищенные (_) и __init__.
                    # Отбрасываем остальные dunder-методы (__dunder__) и приватные (__private).
                    name = item.name
                    if name.startswith("__") and name != "__init__":
                        continue

                    method_symbol = self._build_symbol(item, "method")
                    if method_symbol.breadcrumbs.is_abstract:
                        has_abstract_methods = True

                    symbol.children.append(method_symbol)

            # Если есть абстрактные методы, класс тоже абстрактный
            if has_abstract_methods:
                symbol.breadcrumbs.is_abstract = True

        return symbol


# Re-export metadata utilities to maintain backward compatibility
from .project_metadata import (
    collect_project_metadata,
    calculate_project_hash,
    save_context_metadata_cache,
)

__all__ = [
    "Indexer",
    "GitIgnoreMatcher",
    "collect_project_metadata",
    "calculate_project_hash",
    "save_context_metadata_cache",
]
