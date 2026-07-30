from __future__ import annotations

import re
import subprocess
from pathlib import Path

from ..ai_lint import Rule, LintResult


def get_git_changed_files(base_dir: str) -> list[str]:
    """Возвращает список всех измененных, добавленных и неотслеживаемых файлов в Git.

    Args:
        base_dir: Путь к корню проекта.

    Returns:
        Список абсолютных путей к измененным файлам.
    """
    changed_files = set()
    base_path = Path(base_dir)

    try:
        # 1. Staged изменения
        res_staged = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=str(base_path),
            capture_output=True,
            text=True,
            check=True
        )
        for line in res_staged.stdout.splitlines():
            line = line.strip()
            if line:
                changed_files.add(str((base_path / line).resolve()))

        # 2. Unstaged изменения
        res_unstaged = subprocess.run(
            ["git", "diff", "--name-only"],
            cwd=str(base_path),
            capture_output=True,
            text=True,
            check=True
        )
        for line in res_unstaged.stdout.splitlines():
            line = line.strip()
            if line:
                changed_files.add(str((base_path / line).resolve()))

        # 3. Untracked файлы
        res_untracked = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            cwd=str(base_path),
            capture_output=True,
            text=True,
            check=True
        )
        for line in res_untracked.stdout.splitlines():
            line = line.strip()
            if line:
                changed_files.add(str((base_path / line).resolve()))

    except (subprocess.SubprocessError, FileNotFoundError):
        pass

    return sorted(list(changed_files))


def get_git_new_files(base_dir: str) -> list[str]:
    """Возвращает список всех новых (добавленных или неотслеживаемых) файлов в Git.

    Args:
        base_dir: Путь к корню проекта.

    Returns:
        Список абсолютных путей к новым файлам.
    """
    new_files = set()
    base_path = Path(base_dir)

    try:
        # 1. Staged Added (новые файлы, добавленные в индекс)
        res_staged = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=A"],
            cwd=str(base_path),
            capture_output=True,
            text=True,
            check=True
        )
        for line in res_staged.stdout.splitlines():
            line = line.strip()
            if line:
                new_files.add(str((base_path / line).resolve()))

        # 2. Untracked (неотслеживаемые файлы, которые еще не добавлены)
        res_untracked = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            cwd=str(base_path),
            capture_output=True,
            text=True,
            check=True
        )
        for line in res_untracked.stdout.splitlines():
            line = line.strip()
            if line:
                new_files.add(str((base_path / line).resolve()))

    except (subprocess.SubprocessError, FileNotFoundError):
        pass

    return sorted(list(new_files))


def match_glob(file_path: Path, glob_pattern: str, base_dir: Path) -> bool:
    """Проверяет, подходит ли файл под глоб-шаблон (поддерживает **).

    Args:
        file_path: Абсолютный путь к файлу.
        glob_pattern: Глоб-шаблон (например, "src/chutils/**/*.py").
        base_dir: Базовая директория проекта.

    Returns:
        True, если файл соответствует шаблону, иначе False.
    """
    try:
        rel_path = file_path.relative_to(base_dir)
    except ValueError:
        return False

    rel_str = str(rel_path).replace("\\", "/")
    pattern_str = glob_pattern.replace("\\", "/")

    # Заменяем глоб-символы на маркеры
    pattern_str = pattern_str.replace("**", "_DBLSTAR_")
    pattern_str = pattern_str.replace("*", "_SGLSTAR_")
    pattern_str = pattern_str.replace("?", "_ANYCHAR_")

    # Экранируем спецсимволы регулярных выражений
    escaped = re.escape(pattern_str)

    # Заменяем маркеры на regex эквиваленты
    escaped = re.sub(r'\\?/_DBLSTAR_\\?/', r'(?:/.*)?/', escaped)
    escaped = escaped.replace('_DBLSTAR_', r'.*')
    escaped = escaped.replace('_SGLSTAR_', r'[^/]*')
    escaped = escaped.replace('_ANYCHAR_', r'[^/]')

    regex_str = f"^{escaped}$"
    try:
        return bool(re.match(regex_str, rel_str))
    except Exception:
        return False


def is_file_ignored(file_path: Path) -> bool:
    """Проверяет, содержит ли файл директиву игнорирования правила.

    Args:
        file_path: Путь к проверяемому файлу.

    Returns:
        True, если в файле есть комментарий игнорирования, иначе False.
    """
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        return "chutils:ignore[filedependencysyncrule]" in content.lower().replace(" ", "")
    except Exception:
        return False


class FileDependencySyncRule(Rule):
    """
    Правило контроля синхронизации связанных файлов и документации (FileDependencySyncRule).
    """
    name = "FileDependencySyncRule"
    description = "Проверяет, что при изменении исходных файлов связанные с ними файлы зависимостей также были обновлены."
    severity = "warn"

    def check(self, base_dir: str, files: list[str]) -> list[LintResult]:
        """Выполняет проверку связанных зависимостей.

        Args:
            base_dir: Путь к корню проверяемого проекта.
            files: Список путей к файлам (не используется напрямую, так как мы смотрим Git-изменения).

        Returns:
            Список предупреждений о рассинхронизации.
        """
        results: list[LintResult] = []
        base_path = Path(base_dir)

        # Загружаем карту зависимостей
        dependencies: dict[str, list[str]] = self.config.get("dependencies", {})
        if not dependencies:
            return results

        # Получаем все измененные в Git файлы и новые файлы
        git_changed = get_git_changed_files(base_dir)
        git_new = get_git_new_files(base_dir)
        if not git_changed:
            return results

        # FileDependencySyncRule НАМЕРЕННО ИГНОРИРУЕТ глобальные списки .gitignore, .chutilsignore и [ai-lint] ignore,
        # так как файлы документации (docs/*.md, api_map.md) и схемы могут находиться во внешних/игнорируемых каталогах.
        # Учитывается ТОЛЬКО инлайн-директива: # chutils: ignore[FileDependencySyncRule]
        active_changed = [Path(f_str) for f_str in git_changed if not is_file_ignored(Path(f_str))]
        active_new = [Path(f_str) for f_str in git_new if not is_file_ignored(Path(f_str))]

        # Выполняем проверку по карте зависимостей
        for source_glob, dep_globs in dependencies.items():
            if not isinstance(dep_globs, list):
                dep_globs = [dep_globs]

            is_new_only = source_glob.startswith("new:")
            clean_glob = source_glob[4:] if is_new_only else source_glob

            # Находим файлы-источники (новые или любые измененные)
            source_pool = active_new if is_new_only else active_changed
            matching_sources = [f for f in source_pool if match_glob(f, clean_glob, base_path)]
            if not matching_sources:
                continue

            # Проверяем, изменился ли хотя бы один из зависимых файлов
            has_dep_change = False
            for dep_glob in dep_globs:
                matching_deps = [f for f in active_changed if match_glob(f, dep_glob, base_path)]
                if matching_deps:
                    has_dep_change = True
                    break

            # Если зависимые файлы не изменились, регистрируем предупреждение
            if not has_dep_change:
                trigger_file = str(matching_sources[0])
                action_word = "созданы новые файлы" if is_new_only else "изменены"
                results.append(
                    LintResult(
                        rule_name=self.name,
                        message=(
                            f"Для шаблона '{source_glob}' были {action_word}, но связанные "
                            f"файлы ({', '.join(dep_globs)}) не обновлены. Пожалуйста, синхронизируйте изменения."
                        ),
                        severity=self.severity,
                        file_path=trigger_file,
                        line_number=1,
                        fix_suggestion=f"Обновите или перегенерируйте зависимые файлы: {', '.join(dep_globs)}"
                    )
                )

        return results
