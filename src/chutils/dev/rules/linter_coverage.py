from __future__ import annotations

import re
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

        # Получаем паттерны глобального игнорирования из конфигурации
        import fnmatch
        ignore_patterns: list[str] = []
        raw_ignore = self.config.get("ignore")
        if isinstance(raw_ignore, list):
            ignore_patterns = [str(item) for item in raw_ignore]

        # Регулярное выражение для инлайн-игнорирования
        inline_ignore_pattern = re.compile(
            r'#\s*chutils:\s*ignore\s*\[\s*([^\]]+)\s*\]', re.IGNORECASE
        )

        def is_file_ignored(path: Path) -> bool:
            # 1. Проверяем __pycache__
            if "__pycache__" in path.parts:
                return True

            # 2. Проверяем шаблоны глобального игнорирования из конфига
            try:
                rel_path = path.relative_to(base_path)
            except ValueError:
                return False

            rel_str = str(rel_path).replace("\\", "/")
            for pattern in ignore_patterns:
                if not pattern:
                    continue
                # Проверяем части пути
                for part in rel_path.parts:
                    if fnmatch.fnmatch(part, pattern):
                        return True
                # Проверяем весь относительный путь
                if fnmatch.fnmatch(rel_str, pattern):
                    return True
                if pattern in rel_str:
                    return True

            # 3. Проверяем инлайн-директиву игнорирования в первых 10 строках файла
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    for _ in range(10):
                        line = f.readline()
                        if not line:
                            break
                        match = inline_ignore_pattern.search(line)
                        if match:
                            ignored_rules = [r.strip().lower() for r in match.group(1).split(",")]
                            if "all" in ignored_rules or "lintercoveragerule" in ignored_rules:
                                return True
            except Exception:
                pass

            return False

        # Получаем список всех .py файлов, исключая игнорируемые
        py_files: list[Path] = []
        for p in src_path.glob("**/*.py"):
            if not is_file_ignored(p):
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
