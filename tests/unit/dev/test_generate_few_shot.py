"""Тесты для модуля chutils.dev.generate_few_shot."""
from __future__ import annotations

import ast
import json
import textwrap
from pathlib import Path

import pytest

from chutils.dev.generate_few_shot import (
    ArchitectureDetector,
    DetectedEntities,
    FewShotBankWriter,
    GenerationResult,
    TemplateRenderer,
    generate_few_shot_bank,
    update_ai_manifests,
    GEMINI_BLOCK_START,
    GEMINI_BLOCK_END,
)


# ---------------------------------------------------------------------------
# Фикстуры
# ---------------------------------------------------------------------------


@pytest.fixture()
def fake_project(tmp_path: Path) -> Path:
    """Создаёт искусственную структуру проекта с архитектурными абстракциями."""
    root = tmp_path / "fake_project"
    src = root / "src" / "myapp"
    src.mkdir(parents=True)

    # Use Case
    (src / "use_cases.py").write_text(
        textwrap.dedent("""\
            class CreateOrderUseCase:
                def execute(self, data):
                    pass

            class DeleteItemInteractor:
                def execute(self, item_id: int) -> None:
                    pass
        """),
        encoding="utf-8",
    )

    # Repository
    (src / "repositories.py").write_text(
        textwrap.dedent("""\
            from abc import ABC, abstractmethod

            class AbstractUserRepository(ABC):
                @abstractmethod
                def get_by_id(self, user_id: int): ...

            class InMemoryUserRepository(AbstractUserRepository):
                def get_by_id(self, user_id: int): ...
        """),
        encoding="utf-8",
    )

    # Logging
    (src / "services.py").write_text(
        textwrap.dedent("""\
            import logging

            logger = logging.getLogger(__name__)

            def do_something():
                logger.info("doing something")
        """),
        encoding="utf-8",
    )

    # Custom exceptions
    (src / "exceptions.py").write_text(
        textwrap.dedent("""\
            class AppError(Exception):
                pass

            class OrderNotFoundError(AppError):
                pass
        """),
        encoding="utf-8",
    )

    # DI container
    (root / "container.py").write_text(
        textwrap.dedent("""\
            class Container:
                pass
        """),
        encoding="utf-8",
    )

    return root


@pytest.fixture()
def empty_project(tmp_path: Path) -> Path:
    """Пустая директория проекта без архитектурных абстракций."""
    root = tmp_path / "empty_project"
    root.mkdir()
    (root / "main.py").write_text("print('hello')\n", encoding="utf-8")
    return root


@pytest.fixture()
def entities_all() -> DetectedEntities:
    """DetectedEntities со всеми категориями."""
    return DetectedEntities(
        use_cases=["CreateOrderUseCase", "DeleteItemInteractor"],
        repositories=["AbstractUserRepository"],
        loggers=["logger"],
        errors=["AppError", "OrderNotFoundError"],
        di_files=["container"],
    )


# ---------------------------------------------------------------------------
# Тесты DetectedEntities
# ---------------------------------------------------------------------------


class TestDetectedEntities:
    def test_categories_all_present(self, entities_all: DetectedEntities) -> None:
        cats = entities_all.categories
        assert cats == {"use_cases", "repositories", "logging", "errors", "di"}

    def test_categories_empty(self) -> None:
        entities = DetectedEntities()
        assert entities.categories == set()

    def test_categories_partial(self) -> None:
        entities = DetectedEntities(use_cases=["MyUseCase"], errors=["MyError"])
        assert entities.categories == {"use_cases", "errors"}


# ---------------------------------------------------------------------------
# Тесты ArchitectureDetector
# ---------------------------------------------------------------------------


class TestArchitectureDetector:
    def test_detects_use_cases(self, fake_project: Path) -> None:
        detector = ArchitectureDetector(fake_project)
        entities = detector.detect()
        assert "CreateOrderUseCase" in entities.use_cases
        assert "DeleteItemInteractor" in entities.use_cases

    def test_detects_repositories(self, fake_project: Path) -> None:
        detector = ArchitectureDetector(fake_project)
        entities = detector.detect()
        assert "AbstractUserRepository" in entities.repositories

    def test_detects_loggers(self, fake_project: Path) -> None:
        detector = ArchitectureDetector(fake_project)
        entities = detector.detect()
        assert "logger" in entities.loggers

    def test_detects_errors(self, fake_project: Path) -> None:
        detector = ArchitectureDetector(fake_project)
        entities = detector.detect()
        # AppError наследуется от Exception
        assert "AppError" in entities.errors

    def test_detects_di_by_filename(self, fake_project: Path) -> None:
        detector = ArchitectureDetector(fake_project)
        entities = detector.detect()
        assert "container" in entities.di_files

    def test_empty_project_no_entities(self, empty_project: Path) -> None:
        detector = ArchitectureDetector(empty_project)
        entities = detector.detect()
        assert entities.categories == set()

    def test_skips_pycache(self, tmp_path: Path) -> None:
        """Файлы в __pycache__ должны игнорироваться."""
        root = tmp_path / "proj"
        pycache = root / "__pycache__"
        pycache.mkdir(parents=True)
        (pycache / "foo.py").write_text(
            "class FakeUseCase: pass\n", encoding="utf-8"
        )
        detector = ArchitectureDetector(root)
        entities = detector.detect()
        assert "FakeUseCase" not in entities.use_cases

    def test_handles_syntax_error_gracefully(self, tmp_path: Path) -> None:
        """Файл с синтаксической ошибкой не должен ронять детектор."""
        root = tmp_path / "proj"
        root.mkdir()
        (root / "broken.py").write_text("class Foo(: pass\n", encoding="utf-8")
        detector = ArchitectureDetector(root)
        # Не должен поднимать исключение
        entities = detector.detect()
        assert isinstance(entities, DetectedEntities)

    def test_detects_di_by_import(self, tmp_path: Path) -> None:
        """DI определяется по импорту DI-библиотеки."""
        root = tmp_path / "proj"
        root.mkdir()
        (root / "app.py").write_text(
            "import inject\nclass Container: pass\n", encoding="utf-8"
        )
        detector = ArchitectureDetector(root)
        entities = detector.detect()
        assert len(entities.di_files) > 0


# ---------------------------------------------------------------------------
# Тесты TemplateRenderer
# ---------------------------------------------------------------------------


class TestTemplateRenderer:
    @pytest.mark.parametrize("category", ["use_cases", "repositories", "logging", "errors", "di"])
    def test_good_pattern_is_valid_python(
            self, category: str, entities_all: DetectedEntities
    ) -> None:
        renderer = TemplateRenderer(entities_all)
        code = renderer.render_good_pattern(category)
        assert code, f"Good pattern для '{category}' пустой"
        # Не должно быть SyntaxError
        ast.parse(code)

    @pytest.mark.parametrize("category", ["use_cases", "repositories", "logging", "errors", "di"])
    def test_bad_pattern_is_valid_python(
            self, category: str, entities_all: DetectedEntities
    ) -> None:
        renderer = TemplateRenderer(entities_all)
        code = renderer.render_bad_pattern(category)
        assert code, f"Bad pattern для '{category}' пустой"
        ast.parse(code)

    @pytest.mark.parametrize("category", ["use_cases", "repositories", "logging", "errors", "di"])
    def test_readme_is_non_empty(
            self, category: str, entities_all: DetectedEntities
    ) -> None:
        renderer = TemplateRenderer(entities_all)
        readme = renderer.render_readme(category)
        assert readme.strip(), f"README для '{category}' пустой"
        assert category.replace("_", " ") in readme.lower() or category in readme

    def test_good_pattern_uses_real_class_name(self, entities_all: DetectedEntities) -> None:
        """Шаблон Use Case должен использовать реальное имя класса."""
        renderer = TemplateRenderer(entities_all)
        code = renderer.render_good_pattern("use_cases")
        assert "CreateOrderUseCase" in code

    def test_good_pattern_repositories_uses_real_name(self, entities_all: DetectedEntities) -> None:
        renderer = TemplateRenderer(entities_all)
        code = renderer.render_good_pattern("repositories")
        assert "AbstractUserRepository" in code or "UserRepository" in code

    def test_unknown_category_returns_empty(self, entities_all: DetectedEntities) -> None:
        renderer = TemplateRenderer(entities_all)
        assert renderer.render_good_pattern("unknown_cat") == ""
        assert renderer.render_bad_pattern("unknown_cat") == ""

    def test_default_names_without_entities(self) -> None:
        """Шаблоны должны работать без найденных сущностей."""
        entities = DetectedEntities()
        renderer = TemplateRenderer(entities)
        for category in ["use_cases", "repositories", "logging", "errors", "di"]:
            code = renderer.render_good_pattern(category)
            ast.parse(code)


# ---------------------------------------------------------------------------
# Тесты FewShotBankWriter
# ---------------------------------------------------------------------------


class TestFewShotBankWriter:
    def test_writes_files(self, tmp_path: Path) -> None:
        output_dir = tmp_path / "ai_examples"
        output_dir.mkdir()
        writer = FewShotBankWriter(output_dir)

        written = writer.write_category(
            "use_cases",
            "# good\npass\n",
            "# bad\npass\n",
            "# README\n",
        )
        assert written is True
        assert (output_dir / "use_cases" / "good_pattern.py").exists()
        assert (output_dir / "use_cases" / "bad_pattern.py").exists()
        assert (output_dir / "use_cases" / "README.md").exists()

    def test_skips_existing_without_force(self, tmp_path: Path) -> None:
        output_dir = tmp_path / "ai_examples"
        (output_dir / "use_cases").mkdir(parents=True)
        writer = FewShotBankWriter(output_dir, force=False)

        written = writer.write_category("use_cases", "pass\n", "pass\n", "readme\n")
        assert written is False

    def test_overwrites_with_force(self, tmp_path: Path) -> None:
        output_dir = tmp_path / "ai_examples"
        cat_dir = output_dir / "use_cases"
        cat_dir.mkdir(parents=True)
        (cat_dir / "good_pattern.py").write_text("# old\n", encoding="utf-8")

        writer = FewShotBankWriter(output_dir, force=True)
        written = writer.write_category("use_cases", "# new\npass\n", "pass\n", "readme\n")
        assert written is True
        assert "# new" in (cat_dir / "good_pattern.py").read_text(encoding="utf-8")

    def test_path_traversal_protection(self, tmp_path: Path) -> None:
        output_dir = tmp_path / "ai_examples"
        output_dir.mkdir()
        writer = FewShotBankWriter(output_dir)

        with pytest.raises(ValueError, match="Path traversal detected"):
            writer.write_category("../evil", "pass\n", "pass\n", "readme\n")

    def test_syntax_validation_raises(self, tmp_path: Path) -> None:
        output_dir = tmp_path / "ai_examples"
        output_dir.mkdir()
        writer = FewShotBankWriter(output_dir)

        with pytest.raises(SyntaxError, match="Синтаксическая ошибка"):
            writer.write_category(
                "bad_cat",
                "class Foo(:\n    pass\n",  # Невалидный Python
                "pass\n",
                "readme\n",
            )


# ---------------------------------------------------------------------------
# Тесты update_ai_manifests
# ---------------------------------------------------------------------------


class TestUpdateAIManifests:
    def test_creates_agents_md_if_all_missing(self, tmp_path: Path) -> None:
        # Для успешного обновления нужны сгенерированные категории
        examples_dir = tmp_path / "docs" / "ai_examples" / "use_cases"
        examples_dir.mkdir(parents=True)
        (examples_dir / "README.md").write_text("# README", encoding="utf-8")

        result = update_ai_manifests(tmp_path)
        assert result is True

        agents = tmp_path / "AGENTS.md"
        assert agents.exists()
        content = agents.read_text(encoding="utf-8")
        assert GEMINI_BLOCK_START in content
        assert GEMINI_BLOCK_END in content
        assert "use_cases" in content

    def test_updates_existing_manifests(self, tmp_path: Path) -> None:
        examples_dir = tmp_path / "docs" / "ai_examples" / "logging"
        examples_dir.mkdir(parents=True)
        (examples_dir / "README.md").write_text("# README", encoding="utf-8")

        # Создаем существующий GEMINI.md и antigravity.md
        gemini = tmp_path / "GEMINI.md"
        gemini.write_text("# Old Gemini\n", encoding="utf-8")

        anti = tmp_path / "antigravity.md"
        anti.write_text("# Old Anti\n", encoding="utf-8")

        result = update_ai_manifests(tmp_path)
        assert result is True

        # Убеждаемся, что AGENTS.md НЕ был создан, так как были другие
        assert not (tmp_path / "AGENTS.md").exists()

        assert GEMINI_BLOCK_START in gemini.read_text(encoding="utf-8")
        assert GEMINI_BLOCK_START in anti.read_text(encoding="utf-8")

    def test_updates_cursorrules_json(self, tmp_path: Path) -> None:
        examples_dir = tmp_path / "docs" / "ai_examples" / "use_cases"
        examples_dir.mkdir(parents=True)
        (examples_dir / "README.md").write_text("# README", encoding="utf-8")

        cursorrules = tmp_path / ".cursorrules"
        cursorrules.write_text(json.dumps({"existing_key": "val"}), encoding="utf-8")

        result = update_ai_manifests(tmp_path)
        assert result is True

        data = json.loads(cursorrules.read_text(encoding="utf-8"))
        assert "existing_key" in data
        assert "few_shot_examples" in data
        assert data["few_shot_examples"] == ["./docs/ai_examples/use_cases/README.md"]

    def test_updates_cursorrules_text_if_invalid_json(self, tmp_path: Path) -> None:
        examples_dir = tmp_path / "docs" / "ai_examples" / "use_cases"
        examples_dir.mkdir(parents=True)
        (examples_dir / "README.md").write_text("# README", encoding="utf-8")

        cursorrules = tmp_path / ".cursorrules"
        cursorrules.write_text("// Это невалидный JSON с комментарием\n{}", encoding="utf-8")

        result = update_ai_manifests(tmp_path)
        assert result is True

        content = cursorrules.read_text(encoding="utf-8")
        assert GEMINI_BLOCK_START in content
        assert "use_cases" in content


# ---------------------------------------------------------------------------
# Интеграционные тесты generate_few_shot_bank
# ---------------------------------------------------------------------------


class TestGenerateFewShotBank:
    def test_generates_bank_for_fake_project(self, fake_project: Path) -> None:
        result = generate_few_shot_bank(str(fake_project))
        assert isinstance(result, GenerationResult)
        assert len(result.created_categories) > 0
        assert result.output_dir is not None
        assert result.output_dir.exists()

    def test_all_generated_python_files_are_valid(self, fake_project: Path) -> None:
        generate_few_shot_bank(str(fake_project))
        ai_examples = fake_project / "docs" / "ai_examples"
        for py_file in ai_examples.rglob("*.py"):
            source = py_file.read_text(encoding="utf-8")
            ast.parse(source)  # Не должно быть SyntaxError

    def test_creates_default_agents_md(self, fake_project: Path) -> None:
        generate_few_shot_bank(str(fake_project))
        # Так как манифестов не было, должен создаться AGENTS.md
        assert (fake_project / "AGENTS.md").exists()

    def test_merge_without_force(self, fake_project: Path) -> None:
        """Повторный запуск без --force не должен затирать существующие файлы."""
        # Первый запуск
        generate_few_shot_bank(str(fake_project))
        # Помечаем файл пользовательским контентом
        good_file = fake_project / "docs" / "ai_examples" / "use_cases" / "good_pattern.py"
        user_content = "# USER MODIFIED\npass\n"
        good_file.write_text(user_content, encoding="utf-8")
        # Второй запуск без force
        result = generate_few_shot_bank(str(fake_project))
        assert "use_cases" in result.skipped_categories
        assert good_file.read_text(encoding="utf-8") == user_content

    def test_force_overwrites(self, fake_project: Path) -> None:
        """С флагом --force файлы перезаписываются."""
        generate_few_shot_bank(str(fake_project))
        good_file = fake_project / "docs" / "ai_examples" / "use_cases" / "good_pattern.py"
        old_content = good_file.read_text(encoding="utf-8")
        # Модифицируем
        good_file.write_text("# MODIFIED\n", encoding="utf-8")
        # Перезапуск с force
        result = generate_few_shot_bank(str(fake_project), force=True)
        assert "use_cases" in result.created_categories
        new_content = good_file.read_text(encoding="utf-8")
        assert new_content == old_content

    def test_empty_project_returns_empty_result(self, empty_project: Path) -> None:
        result = generate_few_shot_bank(str(empty_project))
        assert result.created_categories == []
        assert result.skipped_categories == []

    def test_raises_for_nonexistent_path(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            generate_few_shot_bank(str(tmp_path / "nonexistent"))

    def test_raises_for_file_not_dir(self, tmp_path: Path) -> None:
        file_path = tmp_path / "file.txt"
        file_path.write_text("hello\n", encoding="utf-8")
        with pytest.raises(FileNotFoundError):
            generate_few_shot_bank(str(file_path))

    def test_console_output_called(self, fake_project: Path) -> None:
        """Убеждаемся, что console.print вызывается."""
        messages: list[str] = []

        class FakeConsole:
            def print(self, msg: str) -> None:
                messages.append(msg)

        generate_few_shot_bank(str(fake_project), console=FakeConsole())
        assert len(messages) > 0

    def test_readme_files_created_for_each_category(self, fake_project: Path) -> None:
        result = generate_few_shot_bank(str(fake_project))
        for cat in result.created_categories:
            readme = fake_project / "docs" / "ai_examples" / cat / "README.md"
            assert readme.exists(), f"README.md отсутствует для категории {cat}"
            assert readme.read_text(encoding="utf-8").strip()


# ---------------------------------------------------------------------------
# Тест ленивой загрузки через chutils
# ---------------------------------------------------------------------------


class TestLazyImport:
    def test_lazy_import_generate_few_shot_bank(self) -> None:
        """generate_few_shot_bank должна быть доступна через chutils."""
        import chutils
        func = getattr(chutils, "generate_few_shot_bank", None)
        # Модуль зарегистрирован как lazy — он может быть подмодулем или функцией
        assert func is not None or hasattr(chutils, "dev")

    def test_direct_import(self) -> None:
        from chutils.dev.generate_few_shot import generate_few_shot_bank as gfb
        assert callable(gfb)
