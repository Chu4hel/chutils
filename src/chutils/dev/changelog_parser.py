"""
Модуль для парсинга описаний релизов и генерации AI-Changelog контекста.
"""
from __future__ import annotations

import re
from typing import Any

from chutils.dev.version_detector import parse_version_tuple

# Регулярные выражения для определения заголовков секций
BREAKING_PATTERNS = [
    r"breaking\s*changes?",
    r"breaking",
    r"критические\s*изменения",
    r"обратная\s*совместимость",
]
NEW_API_PATTERNS = [
    r"new\s*apis?",
    r"new\s*features?",
    r"added",
    r"новые\s*функции",
    r"добавлено",
    r"новые\s*возможности",
]
DEPRECATION_PATTERNS = [
    r"deprecations?",
    r"deprecated",
    r"устарело",
    r"устаревшие",
]


def parse_release_body(body: str) -> dict[str, list[str]]:
    """Парсит текст описания релиза и выделяет ключевые секции.

    Args:
        body: Текст описания релиза в формате Markdown.

    Returns:
        Словарь со списками строк изменений по категориям.
    """
    sections: dict[str, list[str]] = {
        "breaking_changes": [],
        "new_api": [],
        "deprecations": [],
    }

    if not body:
        return sections

    current_section: str | None = None
    lines = body.splitlines()

    for line in lines:
        line_strip = line.strip()
        if not line_strip:
            continue

        is_header = False
        # Проверяем, является ли строка элементом списка. Если да, она точно не заголовок
        is_list_item = bool(re.match(r"^(\s*[-*+]\s|\s*\d+\.\s)", line_strip))

        if not is_list_item:
            # Очищаем строку от символов заголовков и жирного текста для проверки ключевых слов
            clean_header = line_strip.lstrip("#").strip("*_ ").lower()

            # 1. Проверяем начало секции Breaking Changes
            if any(re.search(pat, clean_header) for pat in BREAKING_PATTERNS) and (
                    line_strip.startswith("#")
                    or line_strip.startswith("**")
                    or line_strip.startswith("*")
                    or clean_header in ["breaking changes", "breaking"]
            ):
                current_section = "breaking_changes"
                is_header = True

            # 2. Проверяем начало секции New API
            elif any(re.search(pat, clean_header) for pat in NEW_API_PATTERNS) and (
                    line_strip.startswith("#")
                    or line_strip.startswith("**")
                    or line_strip.startswith("*")
                    or clean_header in ["new api", "new features", "added"]
            ):
                current_section = "new_api"
                is_header = True

            # 3. Проверяем начало секции Deprecations
            elif any(re.search(pat, clean_header) for pat in DEPRECATION_PATTERNS) and (
                    line_strip.startswith("#")
                    or line_strip.startswith("**")
                    or line_strip.startswith("*")
                    or clean_header in ["deprecations", "deprecated"]
            ):
                current_section = "deprecations"
                is_header = True

            # 4. Если это любой другой заголовок, сбрасываем текущую секцию
            elif line_strip.startswith("#") or (
                    line_strip.startswith("**") and line_strip.endswith("**")
            ):
                current_section = None
                is_header = True

        if is_header:
            continue

        # Собираем строки изменений в текущую секцию
        if current_section is not None:
            # Убираем маркеры списков (-, *, +, цифры)
            clean_line = re.sub(r"^[\s*\-+\d.]+\s*", "", line_strip)
            if clean_line:
                sections[current_section].append(clean_line)

    return sections


def filter_releases_by_version_range(
        releases: list[dict[str, Any]], old_version: str, new_version: str
) -> list[dict[str, Any]]:
    """Фильтрует список релизов, оставляя только версии в диапазоне (old_version, new_version].

    Сортирует релизы от старых к новым.

    Args:
        releases: Полный список релизов от GitHub API.
        old_version: Начальная версия (исключая).
        new_version: Конечная версия (включая).

    Returns:
        Отфильтрованный и отсортированный список релизов.
    """
    filtered: list[dict[str, Any]] = []
    try:
        old_t = parse_version_tuple(old_version)
        new_t = parse_version_tuple(new_version)
    except Exception:
        return []

    for r in releases:
        tag = r.get("tag_name") or r.get("name")
        if not tag:
            continue
        try:
            tag_t = parse_version_tuple(tag)
            if old_t < tag_t <= new_t:
                filtered.append(r)
        except Exception:
            continue

    # Сортируем от старых к новым по кортежу версии
    filtered.sort(key=lambda x: parse_version_tuple(x.get("tag_name") or x.get("name") or ""))
    return filtered


def generate_migration_context_markdown(
        parsed_changelogs: dict[str, list[str]], old_version: str, new_version: str
) -> str:
    """Генерирует Markdown-документ AI Migration Context.

    Args:
        parsed_changelogs: Словарь со всеми собранными строками по секциям.
        old_version: Предыдущая версия.
        new_version: Новая версия.

    Returns:
        Строка с отформатированным Markdown-контентом.
    """
    lines = [
        f"# AI Migration Context: chutils (v{old_version} -> v{new_version})",
        "",
        "Этот файл содержит свод изменений при обновлении версии пакета,",
        "оптимизированный для использования контекстными AI-ассистентами.",
        "",
    ]

    sections_meta = [
        ("Breaking Changes", "breaking_changes", "Критические изменения API или поведения:"),
        ("New API", "new_api", "Новые добавленные возможности, классы и методы:"),
        ("Deprecations", "deprecations", "Устаревшие возможности (deprecations):"),
    ]

    for title, key, desc in sections_meta:
        lines.append(f"## {title}")
        lines.append(f"*{desc}*")
        items = parsed_changelogs.get(key, [])
        if items:
            for item in items:
                lines.append(f"- {item}")
        else:
            lines.append("- *Нет изменений в этой категории.*")
        lines.append("")

    return "\n".join(lines)
