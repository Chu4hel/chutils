from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class DetectedEntities:
    """Результат анализа архитектуры целевого проекта.

    Attrs:
        use_cases: Имена найденных классов Use Case / Interactor.
        repositories: Имена найденных классов репозиториев.
        loggers: Имена переменных / вызовов логгеров.
        errors: Имена найденных пользовательских исключений.
        di_files: Имена файлов с DI-контейнерами.
        categories: Множество активных категорий.
    """

    use_cases: list[str] = field(default_factory=list)
    repositories: list[str] = field(default_factory=list)
    loggers: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    di_files: list[str] = field(default_factory=list)

    @property
    def categories(self) -> set[str]:
        """Возвращает набор активных категорий.

        Returns:
            Множество строк с названиями активных категорий.
        """
        cats: set[str] = set()
        if self.use_cases:
            cats.add("use_cases")
        if self.repositories:
            cats.add("repositories")
        if self.loggers:
            cats.add("logging")
        if self.errors:
            cats.add("errors")
        if self.di_files:
            cats.add("di")
        return cats


@dataclass
class GenerationResult:
    """Результат генерации банка примеров.

    Attrs:
        created_categories: Список созданных (новых) категорий.
        skipped_categories: Список пропущенных категорий (уже существовали).
        manifest_updated: Был ли обновлён/создан GEMINI.md.
        output_dir: Путь к созданному банку примеров.
    """

    created_categories: list[str] = field(default_factory=list)
    skipped_categories: list[str] = field(default_factory=list)
    manifest_updated: bool = False
    output_dir: Path | None = None
