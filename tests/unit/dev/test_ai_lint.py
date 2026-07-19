import pytest

from chutils.dev.ai_lint import Rule, LintResult, LinterEngine, load_custom_rules
from chutils.dev.rules import (
    ManifestRule, DocstringQualityRule, SecurityHardcodeRule,
    ChutilsIntegrationRule, APIMapRule, EnvSyncRule, CodeDecompositionRule,
    APIMapHashRule, FileDependencySyncRule
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
    def __init__(self) -> None:
        \"\"\"Инициализирует класс.\"\"\"
        self._value = 0

    @property
    def value(self) -> int:
        return self._value

    @value.setter
    def value(self, val: int) -> None:
        self._value = val

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
import requests
import httpx
import tempfile
import json
import datetime
from datetime import timezone
from pathlib import Path

logging.info("Test message")
db_host = os.environ.get("DB_HOST")
token = keyring.get_password("system", "user")
Path("test").mkdir(parents=True, exist_ok=True)
Path("test.txt").write_text("hello")
tempfile.mkstemp()
os.replace("src", "dst")
json.dump({"data": 1}, None)
t1 = datetime.datetime.utcnow()
t2 = datetime.datetime.now(timezone.utc)
"""
    file_path = tmp_path / "bad.py"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(bad_code)

    results = rule.check(str(tmp_path), [str(file_path)])
    assert len(results) == 11
    assert any("logging" in r.message for r in results)
    assert any("os.environ" in r.message or "os.getenv" in r.message for r in results)
    assert any("keyring" in r.message for r in results)
    assert any("requests" in r.message for r in results)
    assert any("httpx" in r.message for r in results)
    assert any("mkdir" in r.message for r in results)
    assert any("write_text" in r.message for r in results)
    assert any("паттерн ручной атомарной записи" in r.message for r in results)
    assert any("json.dump" in r.message for r in results)
    assert any(".utcnow()" in r.message for r in results)
    assert any(".now(timezone.utc)" in r.message for r in results)


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


def test_api_map_rule_formats(tmp_path):
    """Тестирует APIMapRule для форматов JSON и Tree."""
    rule = APIMapRule()
    (tmp_path / "src" / "chutils").mkdir(parents=True, exist_ok=True)
    chutils_dir = tmp_path / ".chutils"
    chutils_dir.mkdir(exist_ok=True)

    # 1. Формат JSON: файл отсутствует
    import json
    cache_path = chutils_dir / "context_metadata.json"
    cache_data = {
        "file_path": "my_api.json",
        "format": "json",
        "project_hash": "hash"
    }
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(cache_data, f)

    results = rule.check(str(tmp_path), [])
    assert len(results) == 1
    assert "Файл контекста не найден: my_api.json" in results[0].message

    # 2. Формат JSON: файл устарел
    api_json_path = tmp_path / "my_api.json"
    with open(api_json_path, "w", encoding="utf-8") as f:
        json.dump({"api": []}, f)

    results = rule.check(str(tmp_path), [])
    assert len(results) == 1
    assert "устарел или не соответствует" in results[0].message


def test_env_sync_rule(tmp_path, mocker):
    """Тестирует EnvSyncRule."""
    mock_config = {
        "env_path": "custom.env",
        "example_path": "custom.env.example"
    }
    mocker.patch("chutils.config.dev.load_ai_lint_config", return_value=mock_config)

    rule = EnvSyncRule()

    # 1. Если файлов нет вообще - нет ошибок
    results = rule.check(str(tmp_path), [])
    assert len(results) == 0

    # 2. Если есть .env, но нет .env.example
    env_file = tmp_path / "custom.env"
    env_file.write_text("A=1\n", encoding="utf-8")
    results = rule.check(str(tmp_path), [])
    assert len(results) == 1
    assert "отсутствует шаблон" in results[0].message

    # 3. Если есть .env.example, но нет .env
    env_file.unlink()
    example_file = tmp_path / "custom.env.example"
    example_file.write_text("A=10\n", encoding="utf-8")
    results = rule.check(str(tmp_path), [])
    assert len(results) == 1
    assert "отсутствует локальный" in results[0].message

    # 4. Оба файла есть, но не синхронизированы
    env_file.write_text("A=1\nB=2\n", encoding="utf-8")
    results = rule.check(str(tmp_path), [])
    assert len(results) == 1
    assert "Расхождение в ключах окружения" in results[0].message
    assert "отсутствуют в custom.env.example: B" in results[0].message

    # 5. Оба файла синхронизированы
    example_file.write_text("A=10\nB=\n", encoding="utf-8")
    results = rule.check(str(tmp_path), [])
    assert len(results) == 0


def test_code_decomposition_rule(tmp_path):
    """Тестирует CodeDecompositionRule."""
    rule = CodeDecompositionRule()
    rule.config = {
        "max_file_lines": 10,
        "max_file_classes": 2
    }

    # 1. Файл в пределах нормы
    ok_code = """
class A:
    pass

class B:
    pass
"""
    file_ok = tmp_path / "ok.py"
    file_ok.write_text(ok_code, encoding="utf-8")
    results = rule.check(str(tmp_path), [str(file_ok)])
    assert len(results) == 0

    # 2. Превышение количества строк
    long_code = "\n" * 12
    file_long = tmp_path / "long.py"
    file_long.write_text(long_code, encoding="utf-8")
    results = rule.check(str(tmp_path), [str(file_long)])
    assert len(results) == 1
    assert "превышает ограничение по размеру" in results[0].message
    assert results[0].severity == "warn"

    # 3. Превышение количества классов
    many_classes_code = """
class A: pass
class B: pass
class C: pass
"""
    file_many = tmp_path / "many.py"
    file_many.write_text(many_classes_code, encoding="utf-8")
    results = rule.check(str(tmp_path), [str(file_many)])
    assert len(results) == 1
    assert "содержит слишком много классов" in results[0].message

    # 4. Превышение строк и классов одновременно
    both_exceeded_code = """
class A: pass
class B: pass
class C: pass
""" + ("\n" * 10)
    file_both = tmp_path / "both.py"
    file_both.write_text(both_exceeded_code, encoding="utf-8")
    results = rule.check(str(tmp_path), [str(file_both)])
    assert len(results) == 2
    assert any("превышает ограничение по размеру" in r.message for r in results)
    assert any("содержит слишком много классов" in r.message for r in results)

    # 5. Игнорирование правила через комментарий # chutils: ignore [CodeDecompositionRule]
    ignored_code_1 = """# chutils: ignore [CodeDecompositionRule]
class A: pass
class B: pass
class C: pass
""" + ("\n" * 10)
    file_ignored_1 = tmp_path / "ignored_1.py"
    file_ignored_1.write_text(ignored_code_1, encoding="utf-8")
    results = rule.check(str(tmp_path), [str(file_ignored_1)])
    assert len(results) == 0

    # 6. Игнорирование правила через комментарий # chutils: ignore [all]
    ignored_code_2 = """# chutils: ignore [all]
class A: pass
class B: pass
class C: pass
""" + ("\n" * 10)
    file_ignored_2 = tmp_path / "ignored_2.py"
    file_ignored_2.write_text(ignored_code_2, encoding="utf-8")
    results = rule.check(str(tmp_path), [str(file_ignored_2)])
    assert len(results) == 0

    # 7. Исключение docstrings
    doc_code = '''"""
Module docstring
that spans
multiple lines
"""

def my_func():
    """Function docstring."""
    pass
'''
    file_doc = tmp_path / "doc.py"
    file_doc.write_text(doc_code, encoding="utf-8")

    # Без исключения - файл содержит 9 физических строк
    rule.config = {
        "max_file_lines": 5,
        "max_file_classes": 5
    }
    results = rule.check(str(tmp_path), [str(file_doc)])
    assert len(results) == 1  # Должен ругнуться, так как 9 > 5

    # С исключением докстрингов - докстринги убираются (5 строк у модуля + 1 у функции = 6 строк уходят), остается 3 строки
    rule.config = {
        "max_file_lines": 5,
        "max_file_classes": 5,
        "decomposition_exclude_docstrings": True
    }
    results = rule.check(str(tmp_path), [str(file_doc)])
    assert len(results) == 0  # 3 <= 5

    # С весом docstrings = 0.5 - 6 строк docstrings * 0.5 = 3 + 3 = 6 строк взвешенных. 6 > 5
    rule.config = {
        "max_file_lines": 5,
        "max_file_classes": 5,
        "decomposition_docstrings_weight": 0.5
    }
    results = rule.check(str(tmp_path), [str(file_doc)])
    assert len(results) == 1  # 6 > 5

    # С весом docstrings = 0.2 - 6 * 0.2 = 1.2 + 3 = 4.2 -> округляется до 4. 4 <= 5
    rule.config = {
        "max_file_lines": 5,
        "max_file_classes": 5,
        "decomposition_docstrings_weight": 0.2
    }
    results = rule.check(str(tmp_path), [str(file_doc)])
    assert len(results) == 0  # 4 <= 5


def test_api_map_hash_rule(tmp_path):
    """Тестирует APIMapHashRule."""
    rule = APIMapHashRule()

    # 1. Если директория src/chutils отсутствует - выход без проверки
    results = rule.check(str(tmp_path), [])
    assert len(results) == 0

    # Создаем структуру проекта chutils
    (tmp_path / "src" / "chutils").mkdir(parents=True, exist_ok=True)
    api_map_path = tmp_path / "api_map.md"

    # 2. Если api_map.md не существует - выход без ошибок
    results = rule.check(str(tmp_path), [])
    assert len(results) == 0

    # 3. api_map.md пустой
    api_map_path.write_text("", encoding="utf-8")
    results = rule.check(str(tmp_path), [])
    assert len(results) == 1
    assert "отсутствует блок метаданных" in results[0].message

    # 4. Frontmatter не закрыт
    api_map_path.write_text("---\nproject_version: 1.0\n", encoding="utf-8")
    results = rule.check(str(tmp_path), [])
    assert len(results) == 1
    assert "не закрыт" in results[0].message

    # 5. Отсутствует project_hash
    api_map_path.write_text("---\nproject_version: 1.0\n---\n", encoding="utf-8")
    results = rule.check(str(tmp_path), [])
    assert len(results) == 1
    assert "отсутствует хэш проекта" in results[0].message

    # 6. Хэш совпадает
    from chutils.dev.ast_indexer import calculate_project_hash
    # Создаем python файл для хэширования
    (tmp_path / "src" / "chutils" / "helper.py").write_text("def run(): pass\n", encoding="utf-8")
    correct_hash = calculate_project_hash(tmp_path)
    api_map_path.write_text(f"---\nproject_hash: {correct_hash}\n---\n", encoding="utf-8")
    results = rule.check(str(tmp_path), [])
    assert len(results) == 0

    # 7. Хэш не совпадает
    # Изменяем файл, хэш меняется
    (tmp_path / "src" / "chutils" / "helper.py").write_text("def run(): pass\n# Изменение\n", encoding="utf-8")
    results = rule.check(str(tmp_path), [])
    assert len(results) == 1
    assert "Файл контекста (api_map.md) устарел" in results[0].message
    assert results[0].severity == "warn"

    # 8. Режим staged: если файлы не менялись - проверка пропускается
    rule.staged = True
    results = rule.check(str(tmp_path), ["docs/README.md"])
    assert len(results) == 0

    # Режим staged: если файлы менялись - проверка работает
    results = rule.check(str(tmp_path), ["src/chutils/helper.py"])
    assert len(results) == 1
    assert "Файл контекста (api_map.md) устарел" in results[0].message


def test_api_map_hash_rule_cache(tmp_path):
    """Тестирует APIMapHashRule с использованием кэша .chutils/context_metadata.json."""
    rule = APIMapHashRule()
    (tmp_path / "src" / "chutils").mkdir(parents=True, exist_ok=True)

    # 1. Создаем кэш, указывающий на кастомный JSON-файл
    chutils_dir = tmp_path / ".chutils"
    chutils_dir.mkdir(exist_ok=True)

    import json
    cache_path = chutils_dir / "context_metadata.json"
    cache_data = {
        "file_path": "my_custom_index.json",
        "format": "json",
        "project_hash": "some_old_hash"
    }
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(cache_data, f)

    results = rule.check(str(tmp_path), [])
    assert len(results) == 1
    assert "Файл контекста не найден: my_custom_index.json" in results[0].message

    # 2. Создаем файл my_custom_index.json с несовпадающим хэшем
    custom_file_path = tmp_path / "my_custom_index.json"
    (tmp_path / "src" / "chutils" / "helper.py").write_text("def run(): pass\n", encoding="utf-8")

    custom_data = {
        "metadata": {
            "project_hash": "mismatched_hash"
        },
        "api": []
    }
    with open(custom_file_path, "w", encoding="utf-8") as f:
        json.dump(custom_data, f)

    results = rule.check(str(tmp_path), [])
    assert len(results) == 1
    assert "Файл контекста (my_custom_index.json) устарел" in results[0].message

    # 3. Совпадающий хэш
    from chutils.dev.ast_indexer import calculate_project_hash, save_context_metadata_cache
    correct_hash = calculate_project_hash(tmp_path)

    custom_data["metadata"]["project_hash"] = correct_hash
    with open(custom_file_path, "w", encoding="utf-8") as f:
        json.dump(custom_data, f)

    save_context_metadata_cache(tmp_path, str(custom_file_path), "json", correct_hash)

    results = rule.check(str(tmp_path), [])
    assert len(results) == 0


def test_file_dependency_sync_rule(tmp_path, mocker):
    """Тестирует FileDependencySyncRule."""
    rule = FileDependencySyncRule()
    rule.config = {
        "dependencies": {
            "src/chutils/**/*.py": ["README.md", "docs/api_map.md"]
        }
    }

    # Сценарий 1: Нет измененных файлов
    mocker.patch(
        "chutils.dev.rules.dependency_sync.get_git_changed_files",
        return_value=[]
    )
    mocker.patch(
        "chutils.dev.rules.dependency_sync.get_git_new_files",
        return_value=[]
    )
    results = rule.check(str(tmp_path), [])
    assert len(results) == 0

    # Сценарий 2: Изменен исходный файл, но зависимые файлы не изменились (должно быть предупреждение)
    src_file = tmp_path / "src" / "chutils" / "cli.py"
    src_file.parent.mkdir(parents=True, exist_ok=True)
    src_file.write_text("print('hello')", encoding="utf-8")

    mocker.patch(
        "chutils.dev.rules.dependency_sync.get_git_changed_files",
        return_value=[str(src_file.resolve())]
    )

    results = rule.check(str(tmp_path), [])
    assert len(results) == 1
    assert "были изменены, но связанные файлы" in results[0].message
    assert results[0].file_path == str(src_file.resolve())

    # Сценарий 3: Изменен исходный файл и один из зависимых (все ок, 0 предупреждений)
    dep_file = tmp_path / "README.md"
    dep_file.write_text("Documentation", encoding="utf-8")

    mocker.patch(
        "chutils.dev.rules.dependency_sync.get_git_changed_files",
        return_value=[str(src_file.resolve()), str(dep_file.resolve())]
    )

    results = rule.check(str(tmp_path), [])
    assert len(results) == 0

    # Сценарий 4: Изменен исходный файл, но на него добавлена директива игнорирования
    src_file_ignored = tmp_path / "src" / "chutils" / "ignored.py"
    src_file_ignored.write_text(
        "# chutils: ignore[FileDependencySyncRule]\nprint('ignore')",
        encoding="utf-8"
    )

    mocker.patch(
        "chutils.dev.rules.dependency_sync.get_git_changed_files",
        return_value=[str(src_file_ignored.resolve())]
    )

    results = rule.check(str(tmp_path), [])
    assert len(results) == 0

    # Сценарий 5: Использование new: префикса. Файл изменен, но не является новым
    rule.config = {
        "dependencies": {
            "new:src/chutils/dev/rules/*.py": ["docs/ai_lint.md"]
        }
    }
    rules_file = tmp_path / "src" / "chutils" / "dev" / "rules" / "my_rule.py"
    rules_file.parent.mkdir(parents=True, exist_ok=True)
    rules_file.write_text("print('rule')", encoding="utf-8")

    # Имитируем, что файл изменен, но get_git_new_files возвращает пустой список
    mocker.patch(
        "chutils.dev.rules.dependency_sync.get_git_changed_files",
        return_value=[str(rules_file.resolve())]
    )
    mocker.patch(
        "chutils.dev.rules.dependency_sync.get_git_new_files",
        return_value=[]
    )

    results = rule.check(str(tmp_path), [])
    assert len(results) == 0  # Срабатывать не должно, так как файл не новый

    # Сценарий 6: Использование new: префикса. Добавлен новый файл
    # Имитируем, что файл и изменен, и является новым
    mocker.patch(
        "chutils.dev.rules.dependency_sync.get_git_changed_files",
        return_value=[str(rules_file.resolve())]
    )
    mocker.patch(
        "chutils.dev.rules.dependency_sync.get_git_new_files",
        return_value=[str(rules_file.resolve())]
    )

    results = rule.check(str(tmp_path), [])
    assert len(results) == 1  # Должно сработать предупреждение
    assert "были созданы новые файлы, но связанные файлы" in results[0].message


def test_linter_output_formats(capsys):
    """Тестирует различные форматы вывода и группировки линтера."""
    from chutils.dev.ai_lint import LinterEngine, LintResult

    # Тестовые результаты
    results = [
        LintResult(rule_name="RuleA", message="Message A", severity="error", file_path="file1.py", line_number=10, fix_suggestion="Fix A"),
        LintResult(rule_name="RuleB", message="Message B", severity="warn", file_path="file2.py", line_number=20, fix_suggestion="Fix B"),
        LintResult(rule_name="RuleA", message="Message A2", severity="warn", file_path="file1.py", line_number=30, fix_suggestion="Fix A2"),
    ]

    # 1. Default (обычный) формат, группировка по файлам
    engine_default = LinterEngine({"output_format": "default", "group_by": "file"})
    engine_default.print_results(results)
    captured = capsys.readouterr().out
    assert "file1.py:10" in captured
    assert "file2.py:20" in captured
    assert "Message A" in captured
    assert "Message B" in captured

    # 2. Default формат, группировка по правилам
    engine_rule = LinterEngine({"output_format": "default", "group_by": "rule"})
    engine_rule.print_results(results)
    captured = capsys.readouterr().out
    assert "RuleA" in captured
    assert "RuleB" in captured

    # 3. Table формат (должен пройти без ошибок выполнения)
    engine_table = LinterEngine({"output_format": "table", "group_by": "file"})
    engine_table.print_results(results)
    captured = capsys.readouterr().out
    assert "Файл: file1.py" in captured or "file1.py" in captured

    # 4. Table формат, группировка по правилам
    engine_table_rule = LinterEngine({"output_format": "table", "group_by": "rule"})
    engine_table_rule.print_results(results)
    captured = capsys.readouterr().out
    assert "Правило: RuleA" in captured or "RuleA" in captured
