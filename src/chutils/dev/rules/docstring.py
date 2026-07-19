from __future__ import annotations

import ast
from pathlib import Path

from ..ai_lint import Rule, LintResult


class DocstringVisitor(ast.NodeVisitor):
    """
    Вспомогательный AST-посетитель для проверки docstrings и type hints.
    """

    def __init__(self, file_path: str, rule_name: str) -> None:
        """Инициализирует AST-посетитель docstring'ов.

        Args:
            file_path: Путь к анализируемому файлу.
            rule_name: Название запускаемого правила.
        """
        self.file_path = file_path
        self.rule_name = rule_name
        self.issues: list[LintResult] = []
        self._current_class_doc: str | None = None

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Анализирует класс на наличие docstring.

        Args:
            node: AST-узел определения класса.
        """
        old_class_doc = self._current_class_doc
        self._current_class_doc = ast.get_docstring(node)

        if not node.name.startswith("_"):
            if not self._current_class_doc:
                self.issues.append(
                    LintResult(
                        rule_name=self.rule_name,
                        message=f"У публичного класса {node.name} отсутствует docstring.",
                        severity="error",
                        file_path=self.file_path,
                        line_number=node.lineno,
                        fix_suggestion=f"Добавьте docstring для класса {node.name}."
                    )
                )
        self.generic_visit(node)
        self._current_class_doc = old_class_doc

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Анализирует синхронную функцию на наличие docstring.

        Args:
            node: AST-узел определения функции.
        """
        self._check_func(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Анализирует асинхронную функцию на наличие docstring.

        Args:
            node: AST-узел определения асинхронной функции.
        """
        self._check_func(node)

    def _check_func(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        # Игнорируем перегрузки @overload
        for dec in node.decorator_list:
            if isinstance(dec, ast.Name) and dec.id == "overload":
                return
            if isinstance(dec, ast.Attribute) and dec.attr == "overload":
                return

        is_public = not node.name.startswith("_") or node.name in ("__init__", "__call__")

        is_property = False
        for dec in node.decorator_list:
            if isinstance(dec, ast.Name) and dec.id == "property":
                is_property = True
            elif isinstance(dec, ast.Attribute) and dec.attr in ("setter", "deleter"):
                is_property = True

        doc = ast.get_docstring(node)
        if not is_property and is_public:
            # Для __init__ docstring не нужен, если есть docstring у самого класса
            if node.name == "__init__":
                if not doc and not self._current_class_doc:
                    self.issues.append(
                        LintResult(
                            rule_name=self.rule_name,
                            message="У метода __init__ отсутствует docstring, и у класса нет docstring.",
                            severity="warn",
                            file_path=self.file_path,
                            line_number=node.lineno,
                            fix_suggestion="Добавьте docstring для класса или метода __init__."
                        )
                    )
            else:
                if not doc:
                    self.issues.append(
                        LintResult(
                            rule_name=self.rule_name,
                            message=f"У публичной функции/метода {node.name} отсутствует docstring.",
                            severity="error",
                            file_path=self.file_path,
                            line_number=node.lineno,
                            fix_suggestion=f"Добавьте docstring для {node.name}."
                        )
                    )
                else:
                    # Парсим аргументы из сигнатуры
                    args_names: list[str] = []
                    for arg in node.args.args:
                        if arg.arg not in ("self", "cls"):
                            args_names.append(arg.arg)
                    if node.args.kwarg:
                        args_names.append(node.args.kwarg.arg)
                    if node.args.vararg:
                        args_names.append(node.args.vararg.arg)

                    if args_names:
                        # Проверка наличия раздела аргументов
                        if "Args:" not in doc and "Parameters:" not in doc:
                            self.issues.append(
                                LintResult(
                                    rule_name=self.rule_name,
                                    message=f"Docstring функции {node.name} не содержит раздела аргументов 'Args:'.",
                                    severity="warn",
                                    file_path=self.file_path,
                                    line_number=node.lineno,
                                    fix_suggestion="Добавьте раздел 'Args:' в Google Style для описания параметров."
                                )
                            )
                        else:
                            # Проверка документированности каждого аргумента
                            for arg_name in args_names:
                                if arg_name not in doc:
                                    self.issues.append(
                                        LintResult(
                                            rule_name=self.rule_name,
                                            message=f"Параметр '{arg_name}' функции {node.name} не описан в docstring.",
                                            severity="warn",
                                            file_path=self.file_path,
                                            line_number=node.lineno,
                                            fix_suggestion=f"Опишите параметр '{arg_name}' в разделе 'Args:'."
                                        )
                                    )

                    # Проверка Returns: в docstring при непустом возвращаемом типе
                    has_return = False
                    if node.returns:
                        if isinstance(node.returns, ast.Constant) and node.returns.value is None:
                            pass
                        elif isinstance(node.returns, ast.Name) and node.returns.id == "None":
                            pass
                        else:
                            has_return = True

                    if has_return and "Returns:" not in doc and "Yields:" not in doc:
                        self.issues.append(
                            LintResult(
                                rule_name=self.rule_name,
                                message=f"Docstring функции {node.name} не содержит раздела возвращаемого значения 'Returns:'.",
                                severity="warn",
                                  file_path=self.file_path,
                                line_number=node.lineno,
                                fix_suggestion="Добавьте раздел 'Returns:' в Google Style для описания возвращаемого значения."
                            )
                        )

        # Проверка аннотаций типов параметров (публичные: error, непубличные: warn)
        severity_hints = "error" if is_public else "warn"
        for arg in node.args.args:
            if arg.arg not in ("self", "cls") and not arg.annotation:
                self.issues.append(
                    LintResult(
                        rule_name=self.rule_name,
                        message=f"У параметра '{arg.arg}' функции {node.name} отсутствует аннотация типа.",
                        severity=severity_hints,
                        file_path=self.file_path,
                        line_number=arg.lineno,
                        fix_suggestion=f"Добавьте аннотацию типа для '{arg.arg}'."
                    )
                )

        # Проверка аннотации возвращаемого значения (публичные: error, непубличные: warn)
        if node.name != "__init__" and not node.returns:
            self.issues.append(
                LintResult(
                    rule_name=self.rule_name,
                    message=f"У функции {node.name} отсутствует аннотация возвращаемого значения.",
                    severity=severity_hints,
                    file_path=self.file_path,
                    line_number=node.lineno,
                    fix_suggestion="Добавьте аннотацию возвращаемого типа (например, -> None)."
                )
            )


class DocstringQualityRule(Rule):
    """
    Правило проверки docstrings по стандарту Google Style и type hints.
    """
    name = "DocstringQualityRule"
    description = "Проверяет наличие/качество docstrings (Google Style) и type hints у публичных классов и методов."
    severity = "error"

    def check(self, base_dir: str, files: list[str]) -> list[LintResult]:
        """Выполняет аудит docstrings и аннотаций типов в исходных кодах.

        Args:
            base_dir: Путь к корню проверяемого проекта.
            files: Список путей к файлам проекта.

        Returns:
            Список найденных ошибок форматирования docstrings.
        """
        results: list[LintResult] = []
        for file_path in files:
            if not file_path.endswith(".py"):
                continue
            if "tests" in Path(file_path).parts or "test" in Path(file_path).name.lower() or "setup.py" in Path(
                    file_path).name:
                continue

            try:
                with open(file_path, encoding="utf-8") as f:
                    content = f.read()
                tree = ast.parse(content)
                visitor = DocstringVisitor(file_path, self.name)
                visitor.visit(tree)
                results.extend(visitor.issues)
            except Exception:
                pass
        return results
