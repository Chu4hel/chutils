from __future__ import annotations

from pathlib import Path

from ..ai_lint import Rule, LintResult
from ..constants import AI_MANIFEST_FILENAMES


class ManifestRule(Rule):
    """
    Правило проверки наличия манифестов для ИИ (antigravity.md, agents.md, GEMINI.md).
    """
    name = "ManifestRule"
    description = "Проверяет наличие файлов манифестов ИИ (antigravity.md, agents.md, GEMINI.md) в ключевых директориях."
    severity = "warn"

    def check(self, base_dir: str, files: list[str]) -> list[LintResult]:
        """Выполняет проверку наличия файлов манифеста ИИ.

        Args:
            base_dir: Путь к корню проверяемого проекта.
            files: Список путей к файлам проекта.

        Returns:
            Список найденных предупреждений по манифестам.
        """
        results: list[LintResult] = []
        base_path = Path(base_dir)

        # 1. Проверяем корень проекта
        root_found = False
        for name in AI_MANIFEST_FILENAMES:
            if (base_path / name).exists():
                root_found = True
                break

        if not root_found:
            results.append(
                LintResult(
                    rule_name=self.name,
                    message="Отсутствует корневой файл манифеста ИИ (antigravity.md, agents.md или GEMINI.md).",
                    severity=self.severity,
                    file_path=str(base_path / "antigravity.md"),
                    fix_suggestion="Создайте файл манифеста (например, antigravity.md или agents.md) в корне проекта для описания архитектуры и соглашений для ИИ."
                )
            )

        # 2. Проверяем основные пакеты (первый уровень под src/)
        src_dir = base_path / "src"
        if src_dir.exists():
            for p in src_dir.iterdir():
                if p.is_dir() and (p / "__init__.py").exists():
                    # В режиме staged проверяем только те пакеты под src/, файлы внутри которых изменились.
                    if getattr(self, "staged", False):
                        p_resolved = str(p.resolve())
                        if not any(f.startswith(p_resolved) for f in files):
                            continue

                    pkg_found = False
                    for name in AI_MANIFEST_FILENAMES:
                        if (p / name).exists():
                            pkg_found = True
                            break
                    if not pkg_found:
                        results.append(
                            LintResult(
                                rule_name=self.name,
                                message=f"В основном пакете {p.name} отсутствует файл манифеста ИИ.",
                                severity=self.severity,
                                file_path=str(p / "antigravity.md"),
                                fix_suggestion=f"Рекомендуется добавить файл манифеста (например, antigravity.md или agents.md) в директорию пакета {p.name}."
                            )
                        )
        return results
