from unittest.mock import MagicMock

from chutils.dev.ai_lint import LinterEngine, LintResult, IGNORE_PATTERN


def test_ignore_pattern_regex() -> None:
    """Проверяет корректность регулярного выражения для различных форматов комментариев."""
    # 1. Простой формат
    match = IGNORE_PATTERN.search("x = 1  # chutils: ignore[RuleName]")
    assert match is not None
    assert match.group(1).strip() == "RuleName"

    # 2. Несколько правил через запятую с пробелами
    match = IGNORE_PATTERN.search("y = 2  # chutils: ignore[ Rule1, Rule2 ]")
    assert match is not None
    rules = [r.strip() for r in match.group(1).split(",")]
    assert rules == ["Rule1", "Rule2"]

    # 3. Ключевое слово all
    match = IGNORE_PATTERN.search("z = 3  # chutils: ignore[all]")
    assert match is not None
    assert match.group(1).strip() == "all"

    # 4. Текст обоснования после скобок
    match = IGNORE_PATTERN.search("a = 4  # chutils: ignore[RuleName] -- обоснование ошибки")
    assert match is not None
    assert match.group(1).strip() == "RuleName"

    # 5. Регистронезависимость
    match = IGNORE_PATTERN.search("b = 5  # CHUTILS: IGNORE[RuleName]")
    assert match is not None
    assert match.group(1).strip() == "RuleName"


def test_linter_engine_suppression_logic(tmp_path) -> None:
    """Проверяет логику подавления ошибок через LinterEngine."""
    file_path = tmp_path / "test_file.py"
    file_path.write_text(
        "line 1\n"
        "line 2  # chutils: ignore[RuleA]\n"
        "# chutils: ignore[RuleB]\n"
        "line 4\n"
        "line 5  # chutils: ignore[all]\n"
        "line 6\n",
        encoding="utf-8"
    )

    engine = LinterEngine({"base_dir": str(tmp_path)})

    # Ошибка на строке 2 (игнорируется RuleA)
    r1 = LintResult(rule_name="RuleA", message="Err A", severity="error", file_path=str(file_path), line_number=2)
    # Ошибка на строке 2 другого правила (НЕ игнорируется)
    r2 = LintResult(rule_name="RuleC", message="Err C", severity="error", file_path=str(file_path), line_number=2)
    # Ошибка на строке 4 с блочным игнорированием на строке 3 (игнорируется RuleB)
    r3 = LintResult(rule_name="RuleB", message="Err B", severity="error", file_path=str(file_path), line_number=4)
    # Ошибка на строке 5 (игнорируется все через all)
    r4 = LintResult(rule_name="RuleC", message="Err C", severity="error", file_path=str(file_path), line_number=5)

    # Имитируем запуск
    engine.rules = []
    # Напрямую вызываем фильтрацию
    # Для этого передаем результаты в метод фильтрации
    # (Мы интегрируем фильтрацию в engine.run, но можем протестировать через нее)
    results = [r1, r2, r3, r4]

    # Мокаем правила, чтобы они вернули наш набор результатов
    mock_rule = MagicMock()
    mock_rule.name = "TestRule"
    mock_rule.check.return_value = results
    engine.rules = [mock_rule]

    filtered = engine.run()

    # Должен остаться только r2 (RuleC на строке 2)
    assert len(filtered) == 1
    assert filtered[0].rule_name == "RuleC"
    assert filtered[0].line_number == 2
