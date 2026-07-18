from __future__ import annotations

from pathlib import Path

from chutils.dev.rules.linter_coverage import LinterCoverageRule


def test_linter_coverage_rule_disabled_when_no_dependencies(tmp_path):
    """Тест: LinterCoverageRule не срабатывает, если зависимости не настроены."""
    rule = LinterCoverageRule()
    rule.config = {}  # "dependencies" отсутствует

    # Создаём исходный файл
    src_file = tmp_path / "src" / "chutils" / "some_module.py"
    src_file.parent.mkdir(parents=True, exist_ok=True)
    src_file.write_text("print('hello')", encoding="utf-8")

    results = rule.check(str(tmp_path), [])
    assert len(results) == 0


def test_linter_coverage_rule_disabled_when_rule_not_in_enabled_rules(tmp_path):
    """Тест: LinterCoverageRule не срабатывает, если FileDependencySyncRule отключено."""
    rule = LinterCoverageRule()
    rule.config = {
        "dependencies": {
            "src/chutils/covered.py": ["docs/api.md"]
        },
        "rules": ["LinterCoverageRule"]  # FileDependencySyncRule нет в списке
    }

    # Создаём исходные файлы (один покрыт, другой нет)
    src_dir = tmp_path / "src" / "chutils"
    src_dir.mkdir(parents=True, exist_ok=True)
    (src_dir / "covered.py").write_text("print('covered')", encoding="utf-8")
    (src_dir / "uncovered.py").write_text("print('uncovered')", encoding="utf-8")

    results = rule.check(str(tmp_path), [])
    assert len(results) == 0


def test_linter_coverage_rule_detects_uncovered_files(tmp_path):
    """Тест: LinterCoverageRule выявляет непокрытые файлы."""
    rule = LinterCoverageRule()
    rule.config = {
        "dependencies": {
            "src/chutils/covered.py": ["docs/api.md"],
            "new:src/chutils/new_covered.py": ["docs/api.md"]
        }
    }

    src_dir = tmp_path / "src" / "chutils"
    src_dir.mkdir(parents=True, exist_ok=True)
    (src_dir / "covered.py").write_text("print('covered')", encoding="utf-8")
    (src_dir / "new_covered.py").write_text("print('new')", encoding="utf-8")
    (src_dir / "uncovered.py").write_text("print('uncovered')", encoding="utf-8")

    # Вложенная директория с непокрытым файлом
    nested_dir = src_dir / "nested"
    nested_dir.mkdir(parents=True, exist_ok=True)
    (nested_dir / "deep_uncovered.py").write_text("print('deep')", encoding="utf-8")

    results = rule.check(str(tmp_path), [])

    # Должно быть ровно 2 предупреждения (uncovered.py и deep_uncovered.py)
    assert len(results) == 2
    rule_names = [r.rule_name for r in results]
    assert all(name == "LinterCoverageRule" for name in rule_names)

    uncovered_paths = [Path(r.file_path).name for r in results if r.file_path]
    assert "uncovered.py" in uncovered_paths
    assert "deep_uncovered.py" in uncovered_paths


def test_linter_coverage_rule_fully_covered(tmp_path):
    """Тест: LinterCoverageRule не возвращает предупреждений, если все файлы покрыты."""
    rule = LinterCoverageRule()
    rule.config = {
        "dependencies": {
            "src/chutils/**/*.py": ["docs/api.md"]
        }
    }

    src_dir = tmp_path / "src" / "chutils"
    src_dir.mkdir(parents=True, exist_ok=True)
    (src_dir / "module_a.py").write_text("print('a')", encoding="utf-8")
    (src_dir / "module_b.py").write_text("print('b')", encoding="utf-8")

    results = rule.check(str(tmp_path), [])
    assert len(results) == 0
