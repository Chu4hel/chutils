from __future__ import annotations

import ast
import json
import textwrap
from pathlib import Path
from typing import Protocol

from chutils.fs import ensure_dir, atomic_write
from ..constants import AI_MANIFEST_FILENAMES

GEMINI_BLOCK_START = "<!-- chutils:few-shot-start -->"
GEMINI_BLOCK_END = "<!-- chutils:few-shot-end -->"


class _ConsoleProtocol(Protocol):
    """Минимальный интерфейс Rich Console для вывода сообщений."""

    def print(self, msg: str) -> None:
        """Печатает сообщение в консоль."""
        ...


class FewShotBankWriter:
    """Записывает сгенерированные шаблоны в целевую директорию.

    Args:
        output_dir: Путь к ``docs/ai_examples/`` в целевом проекте.
        force: Если True, перезаписывает существующие категории.
    """

    def __init__(self, output_dir: Path, *, force: bool = False) -> None:
        """Инициализирует FewShotBankWriter.

        Args:
            output_dir: Целевая папка для записи файлов (обычно docs/ai_examples/).
            force: Флаг принудительной перезаписи существующих файлов.
        """
        self._output_dir = output_dir
        self._force = force

    def write_category(
            self,
            category: str,
            good_code: str,
            bad_code: str,
            readme: str,
    ) -> bool:
        """Записывает файлы категории.

        Args:
            category: Название категории (папки).
            good_code: Содержимое ``good_pattern.py``.
            bad_code: Содержимое ``bad_pattern.py``.
            readme: Содержимое ``README.md``.

        Returns:
            True если файлы были записаны, False если категория пропущена.

        Raises:
            ValueError: При нарушении path traversal защиты.
        """
        cat_dir = self._resolve_safe(category)

        if cat_dir.exists() and not self._force:
            return False  # chutils: ignore[ChutilsIntegrationRule]

        ensure_dir(cat_dir)

        self._validate_python_syntax(good_code, f"{category}/good_pattern.py")
        self._validate_python_syntax(bad_code, f"{category}/bad_pattern.py")  # chutils: ignore[ChutilsIntegrationRule]
        # chutils: ignore[ChutilsIntegrationRule]
        atomic_write(cat_dir / "good_pattern.py", good_code)  # chutils: ignore[ChutilsIntegrationRule]
        atomic_write(cat_dir / "bad_pattern.py", bad_code)
        atomic_write(cat_dir / "README.md", readme)

        return True

    def _resolve_safe(self, category: str) -> Path:
        """Возвращает безопасный абсолютный путь к категории.

        Args:
            category: Имя категории.

        Returns:
            Абсолютный путь к директории категории.

        Raises:
            ValueError: Если category содержит попытку path traversal.
        """
        resolved = (self._output_dir / category).resolve()
        output_resolved = self._output_dir.resolve()
        if not str(resolved).startswith(str(output_resolved)):
            raise ValueError(
                f"Path traversal detected: категория '{category}' выходит за пределы '{output_resolved}'"
            )
        return resolved

    @staticmethod
    def _validate_python_syntax(code: str, filename: str) -> None:
        """Проверяет синтаксис Python-кода через ast.parse.

        Args:
            code: Исходный код Python.
            filename: Имя файла (для сообщения об ошибке).

        Raises:
            SyntaxError: Если код содержит синтаксические ошибки.
        """
        try:
            ast.parse(code)
        except SyntaxError as e:
            raise SyntaxError(
                f"Синтаксическая ошибка в шаблоне '{filename}': {e}"
            ) from e


def _build_manifest_block(categories: list[str]) -> str:
    """Строит Markdown-блок ссылок на few-shot банк.

    Args:
        categories: Список категорий.

    Returns:
        Строка с Markdown-блоком для вставки.
    """
    lines = [
        GEMINI_BLOCK_START,
        "",
        "## Few-shot примеры (AI Examples Bank)",
        "",
        "Банк примеров кода для обучения ИИ-агентов стандартам проекта.",
        "Сгенерирован командой `chutils dev generate-few-shot`.",
        "",
    ]
    for cat in sorted(categories):
        lines.append(f"- [{cat}](./docs/ai_examples/{cat}/README.md)")
    lines += ["", GEMINI_BLOCK_END, ""]
    return "\n".join(lines)


def _scan_existing_categories(project_root: Path) -> list[str]:
    """Сканирует папку docs/ai_examples на наличие папок с README.md.

    Args:
        project_root: Путь к корню целевого проекта.

    Returns:
        Список имен найденных категорий.
    """
    examples_dir = project_root / "docs" / "ai_examples"
    if not examples_dir.exists() or not examples_dir.is_dir():
        return []

    categories = []
    for item in examples_dir.iterdir():
        if item.is_dir() and (item / "README.md").exists():
            categories.append(item.name)
    return sorted(categories)


def _update_text_manifest(manifest_path: Path, categories: list[str]) -> bool:
    """Обновляет текстовый/Markdown манифест.

    Args:
        manifest_path: Путь к файлу.
        categories: Список категорий.

    Returns:
        True если успешно обновлен.
    """
    block = _build_manifest_block(categories)
    try:
        content = manifest_path.read_text(encoding="utf-8")
        if GEMINI_BLOCK_START in content and GEMINI_BLOCK_END in content:
            start_idx = content.index(GEMINI_BLOCK_START)
            end_idx = content.index(GEMINI_BLOCK_END) + len(GEMINI_BLOCK_END)
            if end_idx < len(content) and content[end_idx] == "\n":
                end_idx += 1
            new_content = content[:start_idx] + block + content[end_idx:]
        else:
            separator = "\n" if not content.endswith("\n") else ""  # chutils: ignore[ChutilsIntegrationRule]
            new_content = content + separator + "\n" + block
        atomic_write(manifest_path, new_content)
        return True
    except Exception:
        return False


def _update_json_cursorrules(manifest_path: Path, categories: list[str]) -> bool:
    """Обновляет .cursorrules, если он является валидным JSON файлом.

    Если это невалидный JSON, обновляет его как текстовый файл.

    Args:
        manifest_path: Путь к файлу.
        categories: Список категорий.

    Returns:
        True если успешно обновлен.
    """
    try:
        content = manifest_path.read_text(encoding="utf-8")
    except Exception:
        return False

    # Попытка парсинга JSON
    try:
        data = json.loads(content)
        if not isinstance(data, dict):
            # Если это массив или примитив, обработаем как текст
            raise ValueError("Root is not a JSON object")
    except Exception:
        # Невалидный JSON — обрабатываем как текст
        return _update_text_manifest(manifest_path, categories)

    # Обновляем ключ
    paths = [f"./docs/ai_examples/{cat}/README.md" for cat in sorted(categories)]
    data["few_shot_examples"] = paths

    # Записываем обратно с сохранением форматирования (стараемся определить отступы)
    indent = 2
    if "  " in content:
        indent = 2
    if "    " in content:
        indent = 4
    # chutils: ignore[ChutilsIntegrationRule]
    try:
        atomic_write(manifest_path, json.dumps(data, ensure_ascii=False, indent=indent))
        return True
    except Exception:
        return False


def update_ai_manifests(project_root: Path, console: _ConsoleProtocol | None = None) -> bool:
    """Обновляет или создаёт AI-манифесты в корне целевого проекта.

    Ищет существующие манифесты из списка AI_MANIFEST_FILENAMES. Если
    ни одного файла не найдено, создаёт AGENTS.md. Обновляет все найденные.

    Args:
        project_root: Путь к корню целевого проекта.
        console: Консоль для вывода предупреждений.

    Returns:
        True если хотя бы один манифест был успешно обновлен/создан.
    """
    categories = _scan_existing_categories(project_root)
    if not categories:
        return False

    def _warn(msg: str) -> None:
        if console is not None and hasattr(console, "print"):
            console.print(f"[yellow]⚠ {msg}[/yellow]")

    # Поиск существующих файлов в корне проекта
    found_manifests: list[Path] = []
    try:
        for p in project_root.iterdir():
            if p.is_file():
                if p.name.lower() in [m.lower() for m in AI_MANIFEST_FILENAMES]:
                    found_manifests.append(p)
    except Exception as e:
        _warn(f"Ошибка сканирования корня проекта: {e}")
        return False

    updated_any = False

    # Если ни один манифест не найден — создаём AGENTS.md по умолчанию
    if not found_manifests:
        agents_path = project_root / "AGENTS.md"
        base_content = textwrap.dedent("""\
            # Project Agents and AI Instructions

            Этот файл содержит инструкции для ИИ-ассистентов, работающих с проектом.

            ## Общие правила

            - Соблюдайте архитектурные стандарты проекта.
            - Используйте few-shot примеры для написания корректного кода.

            """)
        block = _build_manifest_block(categories)  # chutils: ignore[ChutilsIntegrationRule]
        try:
            atomic_write(agents_path, base_content + "\n" + block)
            found_manifests.append(agents_path)
        except Exception as e:
            _warn(f"Не удалось создать AGENTS.md: {e}")

    # Обновляем все найденные манифесты
    for manifest_path in found_manifests:
        success = False
        if manifest_path.name.lower() == ".cursorrules":
            success = _update_json_cursorrules(manifest_path, categories)
        else:
            success = _update_text_manifest(manifest_path, categories)

        if success:
            updated_any = True
        else:
            _warn(f"Не удалось обновить манифест: {manifest_path.name}")

    return updated_any
