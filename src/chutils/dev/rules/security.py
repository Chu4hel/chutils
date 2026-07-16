from __future__ import annotations

import ast
import re
from pathlib import Path

from ..ai_lint import Rule, LintResult


class SecurityHardcodeRule(Rule):
    """
    Правило обнаружения жестко заданных секретов и ключей.
    """
    name = "SecurityHardcodeRule"
    description = "Поиск захардкоженных токенов, паролей и приватных ключей."
    severity = "error"

    SECRET_REGEXES = {
        "AWS Access Key": re.compile(r"AKIA[0-9A-Z]{16}"),
        "Private Key Header": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
        "Slack Token": re.compile(r"xox[bapr]-[0-9]{12}"),
        "Generic Secret": re.compile(
            r"(?:key|secret|password|passwd|token|credential|pwd)\s*=\s*['\"]([a-zA-Z0-9_\-\.\:\/\+\=\%\@]{16,})['\"]",
            re.IGNORECASE
        )
    }

    def check(self, base_dir: str, files: list[str]) -> list[LintResult]:
        """Выполняет поиск жестко заданных паролей и ключей.

        Args:
            base_dir: Путь к корню проверяемого проекта.
            files: Список путей к файлам проекта.

        Returns:
            Список найденных захардкоженных секретов.
        """
        results: list[LintResult] = []
        for file_path in files:
            if file_path.endswith((".pyc", ".png", ".jpg", ".ico", ".zip", ".tar.gz")):
                continue
            if "tests" in Path(file_path).parts or "test" in Path(file_path).name.lower() or "mock" in Path(
                    file_path).name.lower():
                continue

            try:
                with open(file_path, encoding="utf-8", errors="ignore") as f:
                    content = f.read()
            except Exception:
                continue

            # 1. Текстовое сканирование
            for name, regex in self.SECRET_REGEXES.items():
                for i, line in enumerate(content.splitlines(), 1):
                    if "placeholder" in line.lower() or "your_" in line.lower():
                        continue
                    match = regex.search(line)
                    if match:
                        results.append(
                            LintResult(
                                rule_name=self.name,
                                message=f"Обнаружен потенциальный секрет ({name}).",
                                severity=self.severity,
                                file_path=file_path,
                                line_number=i,
                                fix_suggestion="Вынесите секрет в переменные окружения или задействуйте secret_manager."
                            )
                        )

            # 2. AST сканирование (только для .py)
            if file_path.endswith(".py"):
                try:
                    tree = ast.parse(content)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Assign):
                            for target in node.targets:
                                if isinstance(target, ast.Name):
                                    var_name = target.id.lower()
                                    if any(k in var_name for k in ("key", "secret", "password", "token", "pwd")):
                                        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                                            val = node.value.value
                                            if val and len(val) > 8 and not any(
                                                    p in val.lower() for p in
                                                    ("placeholder", "test", "your_", "default", "env", "config", "_key",
                                                     "_token", "_password", "_pwd")
                                            ):
                                                results.append(
                                                    LintResult(
                                                        rule_name=self.name,
                                                        message=f"Обнаружено жестко заданное значение для секретной переменной '{target.id}'.",
                                                        severity=self.severity,
                                                        file_path=file_path,
                                                        line_number=node.lineno,
                                                        fix_suggestion=f"Не храните секреты в кодовой базе. Перенесите '{target.id}' в окружение."
                                                    )
                                                )
                except Exception:
                    pass
        return results
