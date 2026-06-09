import pytest

from chutils.dev.ai_lint import Rule, LintResult, LinterEngine, load_custom_rules


class DummyRule(Rule):
    name = "DummyRule"
    description = "Test rule"
    severity = "error"

    def check(self, base_dir: str, files: list[str]) -> list[LintResult]:
        results = []
        for file in files:
            if "fail" in file:
                results.append(
                    LintResult(
                        rule_name=self.name,
                        message="File failed DummyRule check",
                        severity=self.severity,
                        file_path=file,
                        line_number=10,
                        fix_suggestion="Rename file to not contain fail"
                    )
                )
        return results


def test_rule_base_class():
    """Проверяет, что базовый класс Rule вызывает NotImplementedError."""
    rule = Rule()
    with pytest.raises(NotImplementedError):
        rule.check("/some/path", [])


def test_should_ignore(tmp_path):
    """Проверяет логику фильтрации игнорируемых путей."""
    config = {
        "base_dir": str(tmp_path),
        "ignore": [".git", "node_modules", "*.tmp", "temp/"]
    }
    engine = LinterEngine(config)

    assert engine.should_ignore(tmp_path / ".git" / "config") is True
    assert engine.should_ignore(tmp_path / "node_modules" / "package.json") is True
    assert engine.should_ignore(tmp_path / "src" / "app.tmp") is True
    assert engine.should_ignore(tmp_path / "temp" / "file.txt") is True
    assert engine.should_ignore(tmp_path / "src" / "app.py") is False


def test_collect_files(tmp_path):
    """Проверяет корректность сбора неигнорируемых файлов в проекте."""
    (tmp_path / "src").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".git").mkdir(parents=True, exist_ok=True)

    with open(tmp_path / "src" / "app.py", "w", encoding="utf-8") as f:
        f.write("")
    with open(tmp_path / "src" / "utils.py", "w", encoding="utf-8") as f:
        f.write("")
    with open(tmp_path / ".git" / "config", "w", encoding="utf-8") as f:
        f.write("")
    with open(tmp_path / "src" / "app.tmp", "w", encoding="utf-8") as f:
        f.write("")

    config = {
        "base_dir": str(tmp_path),
        "ignore": [".git", "*.tmp"]
    }
    engine = LinterEngine(config)
    files = engine.collect_files()

    assert len(files) == 2
    assert any("app.py" in f for f in files)
    assert any("utils.py" in f for f in files)
    assert not any("config" in f for f in files)
    assert not any("app.tmp" in f for f in files)


def test_engine_run(tmp_path):
    """Проверяет выполнение правил линтера движком."""
    (tmp_path / "src").mkdir(parents=True, exist_ok=True)
    with open(tmp_path / "src" / "app_fail.py", "w", encoding="utf-8") as f:
        f.write("")
    with open(tmp_path / "src" / "app_ok.py", "w", encoding="utf-8") as f:
        f.write("")

    config = {
        "base_dir": str(tmp_path),
        "ignore": []
    }
    engine = LinterEngine(config)
    rule = DummyRule()
    engine.rules = [rule]

    results = engine.run()
    assert len(results) == 1
    assert results[0].rule_name == "DummyRule"
    assert "app_fail.py" in results[0].file_path
    assert results[0].line_number == 10
    assert results[0].severity == "error"


def test_print_results_exit_status(tmp_path):
    """Проверяет статус успешности (True/False) в зависимости от режимов (strict, soft)."""
    # 1. Нет результатов - всегда успех
    engine = LinterEngine({"base_dir": str(tmp_path)})
    assert engine.print_results([]) is True

    # 2. Только предупреждение, не strict режим
    warning_result = LintResult(
        rule_name="WarnRule",
        message="Warning occurred",
        severity="warn",
        file_path=str(tmp_path / "app.py")
    )
    engine = LinterEngine({"base_dir": str(tmp_path), "strict": False})
    assert engine.print_results([warning_result]) is True

    # 3. Только предупреждение, strict режим
    engine_strict = LinterEngine({"base_dir": str(tmp_path), "strict": True})
    assert engine_strict.print_results([warning_result]) is False

    # 4. Ошибка, не strict режим
    error_result = LintResult(
        rule_name="ErrRule",
        message="Error occurred",
        severity="error",
        file_path=str(tmp_path / "app.py")
    )
    assert engine.print_results([error_result]) is False

    # 5. Ошибка в soft_mode (всегда успех)
    engine_soft = LinterEngine({"base_dir": str(tmp_path), "soft_mode": True})
    assert engine_soft.print_results([error_result]) is True


def test_load_custom_rules(tmp_path):
    """Проверяет динамическую загрузку кастомных правил из Python файла."""
    rules_file_content = """
from chutils.dev.ai_lint import Rule, LintResult

class CustomRule(Rule):
    name = "CustomRule"
    description = "A custom lint rule"
    severity = "warn"

    def check(self, base_dir: str, files: list[str]) -> list[LintResult]:
        return [LintResult(rule_name=self.name, message="Custom warning", severity=self.severity)]
"""
    rules_path = tmp_path / "my_rules.py"
    with open(rules_path, "w", encoding="utf-8") as f:
        f.write(rules_file_content)

    rules = load_custom_rules(str(rules_path))
    assert len(rules) == 1
    assert rules[0].name == "CustomRule"
    assert rules[0].severity == "warn"

    # Проверяем интеграцию с LinterEngine
    engine = LinterEngine({
        "base_dir": str(tmp_path),
        "custom_rules_path": "my_rules.py"
    })
    engine.load_rules()
    assert len(engine.rules) == 1
    assert engine.rules[0].name == "CustomRule"
