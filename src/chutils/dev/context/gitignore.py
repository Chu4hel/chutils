from __future__ import annotations

import re
from pathlib import Path


class GitIgnoreMatcher:
    """Проверяет соответствие путей правилам .gitignore, .chutilsignore и пользовательским флагам."""

    def __init__(
        self,
        root_path: Path,
        custom_ignore: list[str] | None = None,
        use_gitignore: bool = True,
    ) -> None:
        """Инициализирует GitIgnoreMatcher.

        Args:
            root_path: Корневой путь проекта.
            custom_ignore: Дополнительные паттерны для игнорирования.
            use_gitignore: Флаг необходимости чтения .gitignore файлов.
        """
        self.root_path = root_path
        self.patterns: list[tuple[re.Pattern[str], bool, Path]] = []
        self.use_gitignore = use_gitignore

        if self.use_gitignore:
            self._load_all_gitignore_files(self.root_path)

        self._load_file_rules(self.root_path / ".chutilsignore", self.root_path)

        if custom_ignore:
            for rule in custom_ignore:
                self._add_rule(rule, self.root_path)

    def _load_all_gitignore_files(self, base_dir: Path) -> None:
        """Рекурсивно загружает правила из всех файлов .gitignore в проекте."""
        if not base_dir.exists():
            return

        for gitignore_file in base_dir.rglob(".gitignore"):
            # Пропускаем служебные директории типа .git или .venv при поиске .gitignore
            parts = gitignore_file.relative_to(self.root_path).parts
            if any(p.startswith(".") and p != ".gitignore" for p in parts) or "venv" in parts or "build" in parts:
                continue
            self._load_file_rules(gitignore_file, gitignore_file.parent)

    def _load_file_rules(self, file_path: Path, base_dir: Path) -> None:
        """Загружает правила из указанного файла правил."""
        if not file_path.exists():
            return

        try:
            lines = file_path.read_text(encoding="utf-8").splitlines()
            for line in lines:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                self._add_rule(line, base_dir)
        except Exception:
            pass

    def _add_rule(self, rule_str: str, base_dir: Path) -> None:
        """Добавляет одно правило игнорирования."""
        is_negative = False
        if rule_str.startswith("!"):
            is_negative = True
            rule_str = rule_str[1:]

        regex = self._rule_to_regex(rule_str)
        if regex:
            self.patterns.append((regex, is_negative, base_dir))

    def _rule_to_regex(self, rule: str) -> re.Pattern[str] | None:
        """Преобразует паттерн gitignore в регулярное выражение Python."""
        rule = rule.replace("\\", "/")
        if not rule:
            return None

        anchored = "/" in rule[:-1] if rule.endswith("/") else "/" in rule or rule.startswith("/")

        if rule.startswith("/"):
            rule = rule[1:]

        parts: list[str] = []
        i = 0
        n = len(rule)
        while i < n:
            c = rule[i]
            if c == "*":
                if i + 1 < n and rule[i + 1] == "*":
                    parts.append("__DOUBLE_STAR__")
                    i += 2
                else:
                    parts.append("__STAR__")
                    i += 1
            elif c == "?":
                parts.append("[^/]")
                i += 1
            elif c in (".", "+", "^", "$", "(", ")", "{", "}", "|", "\\"):
                parts.append("\\" + c)
                i += 1
            else:
                parts.append(c)
                i += 1

        regex_str = "".join(parts)
        regex_str = regex_str.replace("__DOUBLE_STAR__", ".*")
        regex_str = regex_str.replace("__STAR__", "[^/]*")

        if rule.endswith("/"):
            regex_str += "?.*"
        else:
            regex_str += "(/.*)?$"

        if anchored:
            regex_str = "^" + regex_str
        else:
            regex_str = "(^|.*/)" + regex_str

        try:
            return re.compile(regex_str)
        except re.error:
            return None

    def matches(self, rel_path: str) -> bool:
        """Возвращает True, если путь должен быть проигнорирован.

        Args:
            rel_path: Относительный путь от корня проекта.

        Returns:
            True, если путь игнорируется, иначе False.
        """
        rel_path_str = rel_path.replace("\\", "/").lstrip("/")
        if not rel_path_str:
            return False

        full_path = self.root_path / rel_path_str
        is_ignored = False

        for pattern, is_negative, base_dir in self.patterns:
            try:
                target_rel = full_path.relative_to(base_dir).as_posix()
            except ValueError:
                continue

            if pattern.search(target_rel):
                is_ignored = not is_negative

        return is_ignored
