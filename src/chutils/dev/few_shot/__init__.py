from __future__ import annotations

from pathlib import Path

from .detector import ArchitectureDetector
from .models import DetectedEntities, GenerationResult
from .renderer import TemplateRenderer
from .writer import (
    FewShotBankWriter,
    update_ai_manifests,
    _ConsoleProtocol,
    GEMINI_BLOCK_START,
    GEMINI_BLOCK_END,
)


def generate_few_shot_bank(
        project_path: str,
        *,
        force: bool = False,
        console: _ConsoleProtocol | None = None,
) -> GenerationResult:
    """Генерирует банк few-shot примеров для целевого проекта.

    Анализирует архитектуру проекта, детектирует ключевые абстракции
    (Use Cases, репозитории, логгеры, исключения, DI-контейнеры) и
    создаёт параметризованные шаблоны ``docs/ai_examples/`` в корне
    целевого проекта.

    Args:
        project_path: Путь к корневой директории целевого проекта.
        force: Если True, существующие категории будут перезаписаны.
        console: Объект Rich Console для вывода статуса (опционально).

    Returns:
        GenerationResult с детализацией созданных и пропущенных категорий.

    Raises:
        FileNotFoundError: Если ``project_path`` не существует.
        ValueError: При нарушении path traversal защиты.
    """
    project_root = Path(project_path).resolve()
    if not project_root.exists():
        raise FileNotFoundError(f"Проект не найден: '{project_root}'")
    if not project_root.is_dir():
        raise FileNotFoundError(f"'{project_root}' — не директория")

    def _print(msg: str) -> None:
        if console is not None and hasattr(console, "print"):
            console.print(msg)

    _print(f"[bold cyan]🔍 Анализ проекта:[/bold cyan] {project_root}")

    # 1. Детектирование
    detector = ArchitectureDetector(project_root)
    entities = detector.detect()
    categories = list(entities.categories)

    if not categories:
        _print("[yellow]⚠ Архитектурные абстракции не обнаружены. Банк примеров не будет создан.[/yellow]")
        return GenerationResult()

    _print(f"[green]✓ Обнаружены категории:[/green] {', '.join(sorted(categories))}")

    # 2. Подготовка директории
    output_dir = project_root / "docs" / "ai_examples"
    from chutils.fs import ensure_dir  # chutils: ignore[ChutilsIntegrationRule]
    ensure_dir(output_dir)

    # 3. Рендер и запись
    renderer = TemplateRenderer(entities)
    writer = FewShotBankWriter(output_dir, force=force)
    result = GenerationResult(output_dir=output_dir)

    for category in sorted(categories):
        good_code = renderer.render_good_pattern(category)
        bad_code = renderer.render_bad_pattern(category)
        readme = renderer.render_readme(category)

        written = writer.write_category(category, good_code, bad_code, readme)
        if written:
            result.created_categories.append(category)
            _print(f"  [green]✓[/green] Создана категория: [bold]{category}[/bold]")
        else:
            result.skipped_categories.append(category)
            _print(
                f"  [yellow]↷[/yellow] Пропущена (используйте --force для перезаписи): [bold]{category}[/bold]"
            )

    # 4. Обновление манифестов ИИ
    result.manifest_updated = update_ai_manifests(project_root, console=console)
    if result.manifest_updated:
        _print("[bold green]✓ Манифесты ИИ обновлены.[/bold green]")
    else:
        _print("[yellow]⚠ Манифесты ИИ не были обновлены.[/yellow]")

    _print(
        f"\n[bold green]✅ Банк few-shot примеров создан:[/bold green] {output_dir}"
    )
    return result


__all__ = [
    "DetectedEntities",
    "GenerationResult",
    "ArchitectureDetector",
    "TemplateRenderer",
    "FewShotBankWriter",
    "generate_few_shot_bank",
    "update_ai_manifests",
    "GEMINI_BLOCK_START",
    "GEMINI_BLOCK_END",
]
