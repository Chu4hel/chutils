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

            # 2. Подсчет строк кода (физических строк)
            lines = content.splitlines()
            line_count = len(lines)

            # 3. Подсчет классов через AST
            class_count = 0
            try:
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        class_count += 1
            except Exception:
                # Если синтаксическая ошибка, пропускаем AST-анализ, но LOC все равно проверили
                pass

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
