import pytest

from chutils.dev.ai_lint import Rule, LintResult, LinterEngine, load_custom_rules
from chutils.dev.rules import (
    ManifestRule, DocstringQualityRule, SecurityHardcodeRule,
    ChutilsIntegrationRule, APIMapRule
)


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
    assert any(r.name == "CustomRule" for r in engine.rules)


# --- Тесты для встроенных правил ---

def test_manifest_rule(tmp_path):
    """Тестирует ManifestRule."""
    rule = ManifestRule()

    # Сценарий 1: Отсутствуют файлы манифестов
    (tmp_path / "src" / "pkg").mkdir(parents=True, exist_ok=True)
    with open(tmp_path / "src" / "pkg" / "__init__.py", "w") as f:
        f.write("")

    results = rule.check(str(tmp_path), [])
    # Ожидаем предупреждение о корневом GEMINI.md и пакете pkg/GEMINI.md
    assert len(results) == 2
    assert any("корневой файл" in r.message for r in results)
    assert any("В основном пакете pkg" in r.message for r in results)

    # Сценарий 2: Добавление альтернативных файлов манифестов (antigravity.md, agents.md)
    with open(tmp_path / "antigravity.md", "w") as f:
        f.write("# Antigravity rules")
    with open(tmp_path / "src" / "pkg" / "agents.md", "w") as f:
        f.write("# Codex agents context")

    results2 = rule.check(str(tmp_path), [])
    assert len(results2) == 0


def test_docstring_quality_rule(tmp_path):
    """Тестирует DocstringQualityRule."""
    rule = DocstringQualityRule()

    # Сценарий 1: Код с нарушениями
    bad_code = """
class MyClass:
    # Нет docstring у класса
    pass

def my_func(a, b: int):
    # Нет docstring у функции, нет типа у 'a', нет возвращаемого типа
    pass

def doc_func(x: str) -> str:
    \"\"\"
    Docstring без раздела Args и Returns.
    \"\"\"
    return x
"""
    file_path = tmp_path / "bad.py"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(bad_code)

    results = rule.check(str(tmp_path), [str(file_path)])
    assert len(results) > 0
    assert any("MyClass" in r.message and "docstring" in r.message for r in results)
    assert any("my_func" in r.message and "docstring" in r.message for r in results)
    assert any("параметра 'a'" in r.message and "аннотация типа" in r.message for r in results)
    assert any("my_func" in r.message and "возвращаемого значения" in r.message for r in results)
    assert any("doc_func" in r.message and "Args:" in r.message for r in results)
    assert any("doc_func" in r.message and "Returns:" in r.message for r in results)

    # Сценарий 2: Корректный код
    good_code = """
class MyGoodClass:
    \"\"\"
    Это класс с документацией.
    \"\"\"
    pass

def good_func(a: int, b: str) -> bool:
    \"\"\"
    Функция с полной аннотацией и docstring в Google Style.

    Args:
        a: Числовой параметр.
        b: Строковый параметр.

    Returns:
        Булевый результат.
    \"\"\"
    return True
"""
    file_path_good = tmp_path / "good.py"
    with open(file_path_good, "w", encoding="utf-8") as f:
        f.write(good_code)

    results_good = rule.check(str(tmp_path), [str(file_path_good)])
    assert len(results_good) == 0


def test_security_hardcode_rule(tmp_path):
    """Тестирует SecurityHardcodeRule."""
    rule = SecurityHardcodeRule()

    # Сценарий 1: Утечка секретов
    bad_code = """
aws_key = "AKIA1234567890123456" # AWS Key Regex
slack_token = "xoxb-123456789012" # Slack Token
my_password = "super-secret-password-hardcoded" # Suspect variable + assignment
"""
    file_path = tmp_path / "bad.py"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(bad_code)

    results = rule.check(str(tmp_path), [str(file_path)])
    assert len(results) >= 3
    assert any("AWS Access Key" in r.message or "AKIA" in r.file_path for r in results)
    assert any("Slack Token" in r.message for r in results)
    assert any("my_password" in r.message or "секретной переменной" in r.message for r in results)

    # Сценарий 2: Безопасный код
    good_code = """
# Безопасно: использование заглушек или чтение из конфига
aws_key = "placeholder_key"
some_val = "ordinary_string"
"""
    file_path_good = tmp_path / "good.py"
    with open(file_path_good, "w", encoding="utf-8") as f:
        f.write(good_code)

    results_good = rule.check(str(tmp_path), [str(file_path_good)])
    assert len(results_good) == 0


def test_chutils_integration_rule(tmp_path):
    """Тестирует ChutilsIntegrationRule."""
    rule = ChutilsIntegrationRule()

    # Сценарий 1: Прямое использование стандартного логирования и os.environ
    bad_code = """
import logging
import os
import keyring

logging.info("Test message")
db_host = os.environ.get("DB_HOST")
token = keyring.get_password("system", "user")
"""
    file_path = tmp_path / "bad.py"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(bad_code)

    results = rule.check(str(tmp_path), [str(file_path)])
    assert len(results) == 3
    assert any("logging" in r.message for r in results)
    assert any("os.environ" in r.message or "os.getenv" in r.message for r in results)
    assert any("keyring" in r.message for r in results)


def test_api_map_rule(tmp_path):
    """Тестирует APIMapRule."""
    rule = APIMapRule()

    # 1. Если нет директории src/chutils, правило ничего не делает
    results = rule.check(str(tmp_path), [])
    assert len(results) == 0

    # 2. Создаем структуру chutils
    (tmp_path / "src" / "chutils").mkdir(parents=True, exist_ok=True)

    # 3. Если нет api_map.md, получаем ошибку
    results_no_file = rule.check(str(tmp_path), [])
    assert len(results_no_file) == 1
    assert "отсутствует файл api_map.md" in results_no_file[0].message

    # 4. Создаем неактуальный api_map.md
    with open(tmp_path / "api_map.md", "w", encoding="utf-8") as f:
        f.write("# Outdated Map")

    results_outdated = rule.check(str(tmp_path), [])
    assert len(results_outdated) == 1
    assert "устарел или не соответствует" in results_outdated[0].message
