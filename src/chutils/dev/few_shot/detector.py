from __future__ import annotations

import ast
from pathlib import Path

from .models import DetectedEntities


class ArchitectureDetector:
    """Анализирует AST целевого проекта для выявления архитектурных абстракций.

    Проходит по всем ``.py``-файлам проекта и собирает:
    - Имена Use Case / Interactor классов
    - Имена репозиториев (абстрактные классы для работы с БД)
    - Имена переменных / экземпляры логгеров
    - Имена пользовательских исключений
    - Наличие файлов DI-контейнеров
    """

    # Ключевые слова для определения архитектурных абстракций
    _USE_CASE_KEYWORDS: frozenset[str] = frozenset(
        {"UseCase", "Interactor", "use_case", "interactor"}
    )
    _REPO_KEYWORDS: frozenset[str] = frozenset(
        {"Repository", "Repo", "AbstractRepository", "BaseRepository"}
    )
    _DI_FILE_NAMES: frozenset[str] = frozenset(
        {"container.py", "di.py", "dependencies.py", "providers.py"}
    )
    _DI_IMPORT_KEYWORDS: frozenset[str] = frozenset(
        {"dependency_injector", "punq", "lagom", "dishka", "inject"}
    )
    _LOGGING_CALLS: frozenset[str] = frozenset(
        {"getLogger", "setup_logger", "get_logger", "logging"}
    )
    _EXCEPTION_BASE_NAMES: frozenset[str] = frozenset(
        {"Exception", "BaseException", "Error", "RuntimeError", "ValueError"}
    )

    def __init__(self, project_root: Path) -> None:
        """Инициализирует ArchitectureDetector.

        Args:
            project_root: Корневая директория исследуемого проекта.
        """
        self._root = project_root

    def detect(self) -> DetectedEntities:
        """Запускает анализ и возвращает найденные сущности.

        Returns:
            DetectedEntities со всеми найденными архитектурными абстракциями.
        """
        entities = DetectedEntities()
        seen_use_cases: set[str] = set()
        seen_repos: set[str] = set()
        seen_loggers: set[str] = set()
        seen_errors: set[str] = set()

        for py_file in self._iter_python_files():
            try:
                source = py_file.read_text(encoding="utf-8", errors="ignore")
                tree = ast.parse(source, filename=str(py_file))
            except SyntaxError:
                continue

            # DI — по имени файла
            if py_file.name in self._DI_FILE_NAMES:
                if py_file.stem not in entities.di_files:
                    entities.di_files.append(py_file.stem)

            # DI — по импортам DI-библиотек
            if not entities.di_files:
                for node in ast.walk(tree):
                    if isinstance(node, (ast.Import, ast.ImportFrom)):
                        module_name = ""
                        if isinstance(node, ast.Import):
                            for alias in node.names:
                                module_name = alias.name.split(".")[0]
                                if module_name in self._DI_IMPORT_KEYWORDS:
                                    entities.di_files.append(py_file.stem)
                                    break
                        elif isinstance(node, ast.ImportFrom) and node.module:
                            module_name = node.module.split(".")[0]
                            if module_name in self._DI_IMPORT_KEYWORDS:
                                entities.di_files.append(py_file.stem)
                        if entities.di_files:
                            break

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    class_name = node.name

                    # Use Cases
                    is_use_case = any(kw in class_name for kw in self._USE_CASE_KEYWORDS)
                    if not is_use_case:
                        for base in node.bases:
                            base_str = self._base_to_str(base)
                            if any(kw in base_str for kw in self._USE_CASE_KEYWORDS):
                                is_use_case = True
                                break
                    if is_use_case and class_name not in seen_use_cases:
                        seen_use_cases.add(class_name)
                        entities.use_cases.append(class_name)

                    # Repositories
                    is_repo = any(kw in class_name for kw in self._REPO_KEYWORDS)
                    if not is_repo:
                        for base in node.bases:
                            base_str = self._base_to_str(base)
                            if any(kw in base_str for kw in self._REPO_KEYWORDS):
                                is_repo = True
                                break
                        # Также проверяем декораторы (абстрактные классы)
                        is_abstract = any(
                            self._decorator_to_str(d) in {"abstractmethod", "ABC"}
                            for d in node.decorator_list
                        )
                        if is_abstract and "Repository" in class_name:
                            is_repo = True
                    if is_repo and class_name not in seen_repos:
                        seen_repos.add(class_name)
                        entities.repositories.append(class_name)

                    # Пользовательские исключения
                    for base in node.bases:
                        base_str = self._base_to_str(base)
                        if any(exc in base_str for exc in self._EXCEPTION_BASE_NAMES):
                            if class_name not in seen_errors:
                                seen_errors.add(class_name)
                                entities.errors.append(class_name)
                            break

                # Логгеры — по вызовам функций и присваиваниям
                elif isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            if isinstance(node.value, ast.Call):
                                func_name = self._call_func_name(node.value)
                                if any(kw in func_name for kw in self._LOGGING_CALLS):
                                    var_name = target.id
                                    if var_name not in seen_loggers:
                                        seen_loggers.add(var_name)
                                        entities.loggers.append(var_name)

        return entities

    def _iter_python_files(self) -> list[Path]:
        """Возвращает список Python-файлов проекта (без скрытых папок и __pycache__).

        Returns:
            Список путей к ``.py``-файлам.
        """
        result: list[Path] = []
        skip_dirs = {
            "__pycache__",
            ".git",
            ".venv",
            "venv",
            "node_modules",
            ".mypy_cache",
            "docs",
        }
        for py_file in self._root.rglob("*.py"):
            if any(part in skip_dirs or part.startswith(".") for part in py_file.parts):
                continue
            result.append(py_file)
        return result

    @staticmethod
    def _base_to_str(base: ast.expr) -> str:
        """Преобразует узел базового класса в строку.

        Args:
            base: AST-узел базового класса.

        Returns:
            Строковое представление базового класса.
        """
        if isinstance(base, ast.Name):
            return base.id
        if isinstance(base, ast.Attribute):
            parts: list[str] = []
            curr: ast.expr = base
            while isinstance(curr, ast.Attribute):
                parts.append(curr.attr)
                curr = curr.value
            if isinstance(curr, ast.Name):
                parts.append(curr.id)
            return ".".join(reversed(parts))
        return ""

    @staticmethod
    def _decorator_to_str(dec: ast.expr) -> str:
        """Преобразует узел декоратора в строку.

        Args:
            dec: AST-узел декоратора.

        Returns:
            Строковое представление декоратора.
        """
        if isinstance(dec, ast.Name):
            return dec.id
        if isinstance(dec, ast.Attribute):
            return dec.attr
        if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Name):
            return dec.func.id
        return ""

    @staticmethod
    def _call_func_name(call: ast.Call) -> str:
        """Извлекает имя функции из вызова.

        Args:
            call: AST-узел вызова функции.

        Returns:
            Имя вызываемой функции.
        """
        if isinstance(call.func, ast.Name):
            return call.func.id
        if isinstance(call.func, ast.Attribute):
            return call.func.attr
        return ""
