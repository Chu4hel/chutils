from chutils.dev.ai_lint import LinterEngine, LintResult


def test_ai_lint_integration_with_real_rule(tmp_path) -> None:
    """Интеграционный тест: создание файла с секретом и проверка его игнорирования."""
    # 1. Создаем файл с нарушением правила SecurityHardcodeRule ( generic secret )
    target_file = tmp_path / "app_code.py"
    target_file.write_text(
        "import os\n"
        "api_key_secret = \"super_secret_value_12345\"\n",
        encoding="utf-8"
    )

    # Инициализируем LinterEngine
    config = {
        "base_dir": str(tmp_path),
        "rules": ["SecurityHardcodeRule"],
    }
    engine = LinterEngine(config)
    engine.load_rules()

    results = engine.run()
    # Должна быть обнаружена ошибка жестко заданного секрета (текстовым и AST сканированием)
    assert len(results) == 2
    assert results[0].rule_name == "SecurityHardcodeRule"
    assert results[0].line_number == 2

    # 2. Добавляем инлайн-комментарий игнорирования
    target_file.write_text(
        "import os\n"
        "api_key_secret = \"super_secret_value_12345\"  # chutils: ignore[SecurityHardcodeRule]\n",
        encoding="utf-8"
    )

    # Сбрасываем кэш
    engine._file_lines_cache.clear()
    results_ignored = engine.run()
    # Теперь ошибка должна быть проигнорирована
    assert len(results_ignored) == 0


def test_ai_lint_edge_cases() -> None:
    """Проверка крайних случаев (отсутствие файлов, некорректные строки)."""
    engine = LinterEngine({"base_dir": "."})

    # 1. Результат без file_path и line_number (должен остаться без изменений)
    r1 = LintResult(rule_name="RuleX", message="Msg X", severity="warn")
    results = [r1]

    # Мокаем правила
    engine.rules = []
    # Фильтруем пустой/фиктивный список
    # Вызов run() соберет файлы, поэтому проверим напрямую фильтрацию через ручную передачу в _get_file_line
    line = engine._get_file_line("", 10)
    assert line is None

    line_oob = engine._get_file_line("non_existent_file.py", 100)
    assert line_oob is None
