from __future__ import annotations

import ast
import re

from ..ai_lint import Rule, LintResult


class CodeDecompositionRule(Rule):
    """
    Правило контроля размера файлов (LOC) и количества классов.
    """
    name = "CodeDecompositionRule"
    description = "Проверяет размер файлов (LOC) и количество классов в них для стимулирования своевременной декомпозиции кода."
    severity = "warn"

    def check(self, base_dir: str, files: list[str]) -> list[LintResult]:
        """Выполняет проверку размера файлов и количества классов.

        Args:
            base_dir: Путь к корню проверяемого проекта.
            files: Список путей к файлам проекта.

        Returns:
            Список найденных предупреждений по размеру/классам.
        """
        results: list[LintResult] = []

        # Загружаем настройки из конфигурации
        config = getattr(self, "config", {}) or {}
        max_file_lines = config.get("max_file_lines", 700)
        max_file_classes = config.get("max_file_classes", 5)
        exclude_docstrings = bool(config.get("decomposition_exclude_docstrings", False))
        docstrings_weight = float(config.get("decomposition_docstrings_weight", 1.0))

        for file_path in files:
            if not file_path.endswith(".py"):
                continue

            try:
                with open(file_path, encoding="utf-8") as f:
                    content = f.read()
            except Exception:
                continue

            # 1. Проверяем инлайн-игнорирование
            ignore_matches = re.findall(r'#\s*chutils:\s*ignore\s*\[\s*([^\]]+)\s*\]', content, re.IGNORECASE)
            should_skip = False
            for val in ignore_matches:
                rules_list = [rule.strip().lower() for rule in val.split(",")]
                if "all" in rules_list or "codedecompositionrule" in rules_list:
                    should_skip = True
                    break
            if should_skip:
                continue

            # 2. Парсим AST для подсчета классов и определения диапазонов docstrings
            class_count = 0
            docstring_ranges: list[tuple[int, int]] = []

            def _is_string_constant(n: ast.AST) -> bool:
                if isinstance(n, ast.Constant):
                    return isinstance(n.value, str)
                # Fallback для старых версий Python
                if hasattr(ast, "Str") and isinstance(n, getattr(ast, "Str")):
                    return True
                return False

            try:
                tree = ast.parse(content)
                # Собираем docstrings модуля
                if tree.body:
                    first = tree.body[0]
                    if isinstance(first, ast.Expr) and _is_string_constant(first.value):
                        start = getattr(first, "lineno", None)
                        end = getattr(first, "end_lineno", None)
                        if start is not None and end is not None:
                            docstring_ranges.append((start, end))

                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        class_count += 1
                        # Собираем docstrings класса
                        if node.body:
                            first = node.body[0]
                            if isinstance(first, ast.Expr) and _is_string_constant(first.value):
                                start = getattr(first, "lineno", None)
                                end = getattr(first, "end_lineno", None)
                                if start is not None and end is not None:
                                    docstring_ranges.append((start, end))
                    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        # Собираем docstrings функций
                        if node.body:
                            first = node.body[0]
                            if isinstance(first, ast.Expr) and _is_string_constant(first.value):
                                start = getattr(first, "lineno", None)
                                end = getattr(first, "end_lineno", None)
                                if start is not None and end is not None:
                                    docstring_ranges.append((start, end))
            except Exception:
                # Если синтаксическая ошибка, пропускаем AST-анализ, но классы и docstring-фильтрацию пропускаем
                pass

            # 3. Подсчет строк кода с учетом веса docstrings
            lines = content.splitlines()
            total_lines = len(lines)

            # Определяем, какие строки относятся к docstrings (1-indexed)
            docstring_lines_set = set()
            for start, end in docstring_ranges:
                for idx in range(start, end + 1):
                    docstring_lines_set.add(idx)

            # Вычисляем взвешенное количество строк
            weighted_line_count = 0.0
            for idx in range(1, total_lines + 1):
                if idx in docstring_lines_set:
                    if exclude_docstrings:
                        continue
                    weighted_line_count += docstrings_weight
                else:
                    weighted_line_count += 1.0

            # Округляем до целого для наглядности в выводе
            line_count = int(weighted_line_count)

            # Проверка превышения количества строк
            if line_count > max_file_lines:
                results.append(
                    LintResult(
                        rule_name=self.name,
                        message=f"Файл превышает ограничение по размеру: {line_count} строк (максимум {max_file_lines}).",
                        severity=self.severity,
                        file_path=file_path,
                        line_number=1,
                        fix_suggestion="Разделите файл на несколько меньших модулей."
                    )
                )

            # Проверка превышения количества классов
            if class_count > max_file_classes:
                results.append(
                    LintResult(
                        rule_name=self.name,
                        message=f"Файл содержит слишком много классов: {class_count} (максимум {max_file_classes}).",
                        severity=self.severity,
                        file_path=file_path,
                        line_number=1,
                        fix_suggestion="Разнесите классы по отдельным файлам."
                    )
                )

        return results
