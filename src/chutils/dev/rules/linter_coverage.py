from __future__ import annotations

from pathlib import Path
from typing import Any

from .dependency_sync import match_glob
from ..ai_lint import Rule, LintResult


class LinterCoverageRule(Rule):
    """
    Правило контроля покрытия исходного кода правилами отслеживания зависимостей (LinterCoverageRule).
    """
    name = "LinterCoverageRule"
    description = "Проверяет, что все исходные файлы проекта охвачены правилами зависимостей в ai-lint.toml."
    severity = "warn"

    def check(self, base_dir: str, files: list[str]) -> list[LintResult]:
        """Выполняет проверку покрытия исходного кода правилами зависимостей.

        Args:
            base_dir: Путь к корню проверяемого проекта.
            files: Список файлов (не используется напрямую, т.к. сканируется src/).

        Returns:
            Список предупреждений о непокрытых файлах.
        """
        results: list[LintResult] = []
        base_path = Path(base_dir)

        # Проверяем, настроено ли отслеживание зависимостей
        dependencies: dict[str, Any] = self.config.get("dependencies", {})
        if not dependencies:
            # Если отслеживание зависимостей не сконфигурировано, правило не работает
            return results

        # Проверяем, включено ли само правило FileDependencySyncRule
        enabled_rules = self.config.get("rules")
        if isinstance(enabled_rules, list):
            enabled_names = [str(name) for name in enabled_rules]
            if "FileDependencySyncRule" not in enabled_names:
                # Если основное правило отслеживания выключено в конфиге, то и покрытие проверять не нужно
                return results

        # Собираем все python-файлы исходного кода chutils
        src_path = base_path / "src" / "chutils"
        if not src_path.exists():
            return results

        # Получаем список всех .py файлов, исключая __pycache__ и временные файлы
        py_files: list[Path] = []
        for p in src_path.glob("**/*.py"):
            if "__pycache__" in p.parts:
                continue
            py_files.append(p)

        # Проверяем каждый файл на покрытие хотя бы одним глоб-шаблоном из dependencies
        # Ключи могут быть обычными глоб-шаблонами или начинаться с "new:"
        patterns: list[str] = []
        for key in dependencies.keys():
            pattern = key[4:] if key.startswith("new:") else key
            patterns.append(pattern)

        uncovered_files: list[Path] = []
        for py_file in py_files:
            # Проверяем, покрыт ли файл хотя бы одним шаблоном
            covered = False
            for pattern in patterns:
                if match_glob(py_file, pattern, base_path):
                    covered = True
                    break

            if not covered:
                uncovered_files.append(py_file)

        # 5. Генерируем предупреждения для непокрытых файлов
        for file in uncovered_files:
            try:
                rel_path = file.relative_to(base_path)
            except ValueError:
                rel_path = file

            results.append(
                LintResult(
                    rule_name=self.name,
                    message=(
                        f"Файл '{rel_path}' не покрыт ни одним правилом отслеживания зависимостей "
                        f"в секции [dependencies] файла ai-lint.toml."
                    ),
                    severity=self.severity,
                    file_path=str(file.resolve()),
                    line_number=1,
                    fix_suggestion=(
                        f"Добавьте глоб-шаблон для '{rel_path}' в секцию [dependencies] "
                        f"файла ai-lint.toml и укажите связанные файлы документации."
                    )
                )
            )

        return results
