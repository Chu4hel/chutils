"""
Ядро движка проверки AI-готовности (ai-lint).
Определяет базовые классы Rule, LintResult и LinterEngine.
"""

from __future__ import annotations

import fnmatch
import importlib.util
import os
import re
from pathlib import Path

IGNORE_PATTERN = re.compile(r'#\s*chutils:\s*ignore\s*\[\s*([^\]]+)\s*\]', re.IGNORECASE)

try:
    from pydantic import BaseModel

    HAS_PYDANTIC = True
except ImportError:
    HAS_PYDANTIC = False


    class BaseModel:  # type: ignore[no-redef]
        """Временный базовый класс-заглушка при отсутствии Pydantic."""
        pass

if HAS_PYDANTIC:
    class LintResult(BaseModel):
        """
        Представляет результат одной проверки правила.
        """
        rule_name: str
        message: str
        severity: str
        file_path: str | None = None
        line_number: int | None = None
        fix_suggestion: str | None = None
else:
    class LintResult:  # type: ignore[no-redef]
        """
        Представляет результат одной проверки правила (Fallback версия без Pydantic).
        """

        def __init__(
                self,
                rule_name: str,
                message: str,
                severity: str,
                file_path: str | None = None,
                line_number: int | None = None,
                fix_suggestion: str | None = None,
        ) -> None:
            """Инициализирует fallback-результат проверки правила.

            Args:
                rule_name: Название правила.
                message: Сообщение об ошибке/предупреждении.
                severity: Критичность проблемы.
                file_path: Опциональный путь к файлу.
                line_number: Номер строки.
                fix_suggestion: Рекомендация по исправлению.
            """
            self.rule_name = rule_name
            self.message = message
            self.severity = severity
            self.file_path = file_path
            self.line_number = line_number
            self.fix_suggestion = fix_suggestion


class Rule:
    """
    Абстрактный базовый класс для всех правил линтера.
    """
    name: str = ""
    description: str = ""
    severity: str = "error"  # Может быть "error" или "warn"

    def check(self, base_dir: str, files: list[str]) -> list[LintResult]:
        """
        Выполняет проверку правила по списку файлов.

        Args:
            base_dir: Путь к корню проверяемого проекта.
            files: Список абсолютных путей к файлам проекта.

        Returns:
            Список объектов LintResult с найденными проблемами.
        """
        raise NotImplementedError("Каждое правило должно реализовывать метод check.")


def load_custom_rules(custom_rules_path: str) -> list[Rule]:
    """
    Динамически загружает пользовательские правила из указанного файла.

    Args:
        custom_rules_path: Путь к файлу с правилами (например, .chutils/lint_rules.py).

    Returns:
        Список загруженных экземпляров пользовательских правил.
    """
    rules: list[Rule] = []
    path = Path(custom_rules_path)
    if not path.exists():
        return rules

    try:
        spec = importlib.util.spec_from_file_location("custom_lint_rules", str(path))
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            # Находим все классы в модуле, которые наследуют Rule
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if isinstance(attr, type) and issubclass(attr, Rule) and attr is not Rule:
                    rules.append(attr())
    except Exception:
        # В случае ошибок загрузки возвращаем то, что удалось загрузить
        pass
    return rules


class LinterEngine:
    """
    Движок линтера, координирующий сбор файлов, загрузку правил и их выполнение.
    """

    def __init__(self, config: dict[str, str | bool | list[str] | None]) -> None:
        """
        Инициализирует движок с переданной конфигурацией.

        Args:
            config: Словарь настроек линтера.
        """
        self.config = config
        self.base_dir = Path(str(config.get("base_dir") or os.getcwd())).resolve()

        # Безопасное приведение типов для ignore
        raw_ignore = config.get("ignore")
        if isinstance(raw_ignore, list):
            self.ignore_patterns = [str(item) for item in raw_ignore]
        else:
            self.ignore_patterns = []

        self.strict = bool(config.get("strict", False))
        self.soft_mode = bool(config.get("soft_mode", False))
        self.staged = bool(config.get("staged", False))
        self.rules: list[Rule] = []
        self._file_lines_cache: dict[str, list[str]] = {}

    def _get_file_line(self, file_path: str, line_number: int) -> str | None:
        """
        Возвращает строку из файла по 1-индексному номеру строки с использованием кэша.
        Безопасно обрабатывает ошибки чтения файлов и некорректные номера строк.
        """
        if not file_path or line_number < 1:
            return None

        try:
            resolved_path = str(Path(file_path).resolve())
        except Exception:
            return None

        if resolved_path not in self._file_lines_cache:
            try:
                with open(resolved_path, "r", encoding="utf-8", errors="ignore") as f:
                    self._file_lines_cache[resolved_path] = f.readlines()
            except Exception:
                self._file_lines_cache[resolved_path] = []

        lines = self._file_lines_cache[resolved_path]
        if 1 <= line_number <= len(lines):
            return lines[line_number - 1]
        return None

    def load_rules(self) -> None:
        """
        Загружает правила (встроенные и кастомные).
        """
        from .rules import (
            ManifestRule, DocstringQualityRule, SecurityHardcodeRule,
            ChutilsIntegrationRule, APIMapRule, EnvSyncRule, CodeDecompositionRule,
            APIMapHashRule
        )

        # Регистрируем встроенные правила
        self.rules = [
            ManifestRule(),
            DocstringQualityRule(),
            SecurityHardcodeRule(),
            ChutilsIntegrationRule(),
            APIMapRule(),
            EnvSyncRule(),
            CodeDecompositionRule(),
            APIMapHashRule()
        ]

        # Загружаем кастомные правила
        custom_path = self.config.get("custom_rules_path")
        if isinstance(custom_path, str) and custom_path:
            abs_custom_path = Path(self.base_dir) / custom_path
            if abs_custom_path.exists():
                self.rules.extend(load_custom_rules(str(abs_custom_path)))

    def should_ignore(self, path: Path) -> bool:
        """
        Проверяет, должен ли данный путь быть проигнорирован.

        Args:
            path: Проверяемый путь.

        Returns:
            True, если путь соответствует какому-либо шаблону игнорирования.
        """
        try:
            rel_path = path.relative_to(self.base_dir)
        except ValueError:
            return False

        parts = rel_path.parts
        for pattern in self.ignore_patterns:
            if not pattern:
                continue
            for part in parts:
                if fnmatch.fnmatch(part, pattern):
                    return True
            if fnmatch.fnmatch(str(rel_path).replace("\\", "/"), pattern):
                return True
            if pattern in str(rel_path).replace("\\", "/"):
                return True
        return False

    def collect_files(self) -> list[str]:
        """
        Собирает все неигнорируемые файлы в проекте (учитывая флаг staged).

        Returns:
            Список абсолютных путей к файлам.
        """
        if self.staged:
            return self.collect_staged_files()
        return self.collect_all_files()

    def collect_staged_files(self) -> list[str]:
        """
        Собирает список измененных и добавленных файлов, подготовленных к коммиту (staged) в Git.

        Returns:
            Список абсолютных путей к файлам.
        """
        import subprocess
        from chutils.cli_utils import get_console
        console = get_console()

        try:
            cmd = ["git", "diff", "--cached", "--name-only", "--diff-filter=d"]
            result = subprocess.run(
                cmd,
                cwd=str(self.base_dir),
                capture_output=True,
                text=True,
                check=True
            )
            relative_paths = [line.strip() for line in result.stdout.splitlines() if line.strip()]

            absolute_paths: list[str] = []
            for rel_path in relative_paths:
                file_path = Path(self.base_dir) / rel_path
                if not self.should_ignore(file_path):
                    absolute_paths.append(str(file_path.resolve()))
            return absolute_paths
        except (subprocess.SubprocessError, FileNotFoundError) as e:
            console.print(
                f"[yellow]⚠ Предупреждение: не удалось получить список staged файлов через Git ({e}). "
                f"Выполняется полное сканирование.[/yellow]"
            )
            return self.collect_all_files()

    def collect_all_files(self) -> list[str]:
        """
        Собирает абсолютно все неигнорируемые файлы в проекте.

        Returns:
            Список абсолютных путей к файлам.
        """
        all_files: list[str] = []
        for root, dirs, filenames in os.walk(self.base_dir):
            pruned_dirs: list[str] = []
            for d in dirs:
                dir_path = Path(root) / d
                if not self.should_ignore(dir_path):
                    pruned_dirs.append(d)
            dirs[:] = pruned_dirs

            for filename in filenames:
                file_path = Path(root) / filename
                if not self.should_ignore(file_path):
                    all_files.append(str(file_path.resolve()))
        return all_files

    def run(self) -> list[LintResult]:
        """
        Запускает все включенные правила на собранных файлах.

        Returns:
            Список результатов проверок с найденными ошибками и предупреждениями.
        """
        if not self.rules:
            self.load_rules()
        files = self.collect_files()

        results: list[LintResult] = []
        # Фильтруем правила, если в конфигурации явно задан список активных правил
        config_rules = self.config.get("rules")
        enabled_names: list[str] = []
        if isinstance(config_rules, list):
            enabled_names = [str(name) for name in config_rules]

        for rule in self.rules:
            if enabled_names and rule.name not in enabled_names:
                continue

            try:
                rule.staged = self.staged
                rule.config = self.config
                rule_results = rule.check(str(self.base_dir), files)
                results.extend(rule_results)
            except Exception as e:
                results.append(
                    LintResult(
                        rule_name=rule.name,
                        message=f"Ошибка при выполнении правила {rule.name}: {str(e)}",
                        severity="error"
                    )
                )

        # Фильтруем результаты на основе комментариев инлайн-игнорирования
        filtered_results: list[LintResult] = []
        for r in results:
            if not r.file_path or r.line_number is None:
                filtered_results.append(r)
                continue

            ignored = False
            for ln in (r.line_number, r.line_number - 1):
                line_text = self._get_file_line(r.file_path, ln)
                if not line_text:
                    continue

                match = IGNORE_PATTERN.search(line_text)
                if match:
                    rules_str = match.group(1)
                    rules_list = [rule.strip().lower() for rule in rules_str.split(",")]
                    if "all" in rules_list or r.rule_name.lower() in rules_list:
                        ignored = True
                        break

            if not ignored:
                filtered_results.append(r)

        return filtered_results

    def print_results(self, results: list[LintResult]) -> bool:
        """
        Выводит результаты работы линтера в консоль и возвращает статус завершения.

        Args:
            results: Список результатов.

        Returns:
            True, если проверка успешна (нет критических ошибок в строгом режиме/обычном),
            False в противном случае.
        """
        from chutils.cli_utils import get_console
        console = get_console()

        if not results:
            console.print("[green]✓ Все проверки пройдены! Код готов к работе с AI.[/green]")
            return True

        errors_count = 0
        warnings_count = 0

        # Сортируем результаты по путям файлов, критичности и строкам
        sorted_results = sorted(
            results,
            key=lambda r: (r.file_path or "", r.severity, r.line_number or 0)
        )

        for r in sorted_results:
            color = "red" if r.severity == "error" else "yellow"
            severity_str = f"[{color}]{r.severity.upper()}[/{color}]"

            loc_str = ""
            if r.file_path:
                try:
                    rel_file = str(Path(r.file_path).relative_to(self.base_dir))
                except ValueError:
                    rel_file = r.file_path
                loc_str = f"{rel_file}"
                if r.line_number is not None:
                    loc_str += f":{r.line_number}"
                loc_str = f"[cyan]{loc_str}[/cyan]: "

            rule_str = f"[blue][{r.rule_name}][/blue]"
            console.print(f"{loc_str}{severity_str} {rule_str} {r.message}")
            if r.fix_suggestion:
                console.print(f"    [dim]Рекомендация: {r.fix_suggestion}[/dim]")

            if r.severity == "error":
                errors_count += 1
            elif r.rule_name != "APIMapHashRule":
                warnings_count += 1

        console.rule("Итоги аудита")
        summary_msg = f"Найдено проблем: {len(results)} (Ошибок: {errors_count}, Предупреждений: {warnings_count})"
        if errors_count > 0:
            console.print(f"[red]✗ {summary_msg}[/red]")
        else:
            console.print(f"[yellow]⚠ {summary_msg}[/yellow]")

        if self.soft_mode:
            return True
        if errors_count > 0:
            return False
        if self.strict and warnings_count > 0:
            return False
        return True
