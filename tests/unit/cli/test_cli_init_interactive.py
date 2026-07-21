import os
from pathlib import Path

def test_cli_init_interactive_all_yes(cli_runner, config_fs, mocker):
    """Проверяет интерактивный опрос в init, когда на все вопросы отвечают 'y'."""
    fs, project_root = config_fs
    
    # 1. Проект
    # 2. Перезаписать y (по умолчанию)
    # 3. Настроить конфигурацию Базы Данных (Database)? y
    # 4. Инициализировать директорию миграций Alembic (migrations/)? y
    # 5. Настроить криптографический аудит-лог (chutils.audit)? y
    # 6. Настроить интеграцию с облачными провайдерами секретов (AWS/GCP)? y
    # 7. Создать декларативные файлы окуржения .env и .env.example? y
    # 8. Сгенерировать AI-Ready конфигурацию (ai-lint.toml, GEMINI.md)? y
    # 9. Добавить шаблон настройки экспорта метрик Prometheus? y
    # 10. Сгенерировать GitHub Actions CI workflow? y
    # 11. Проверить скорость PyPI-зеркал и настроить оптимальное зеркало? y
    # 12. Настроить модуль диагностики здоровья? y
    # 13. Развернуть скелет Clean Architecture? y
    # 14. Имя первого Clean Arch модуля: my_first_module
    answers = [
        "InteractiveProj", "y", "y", "y", "y", "y", "y", "y", "y", "y", "y", "y", "my_first_module"
    ]
    mocker.patch("builtins.input", side_effect=answers)

    # Изолируем вызовы внешних инструментов или убираем моки
    mocker.patch("chutils.commands.pypi.measure_mirror", return_value={
        "url": "https://pypi.org/simple/", "available": True, "latency_ms": 10.0, "download_speed_kbs": 1000.0, "error": None
    })

    result = cli_runner.invoke(["init"])
    assert result.exit_code == 0
    
    # Проверяем файлы
    assert os.path.exists("config.yml")
    assert os.path.exists(".env")
    assert os.path.exists(".env.example")
    assert os.path.exists("ai-lint.toml")
    assert os.path.exists("GEMINI.md")
    assert os.path.exists(".github/workflows/ci.yml")
    assert os.path.exists("health.py")
    assert os.path.exists("migrations/env.py")
    assert os.path.exists("src/my_first_module/__init__.py")

    with open("config.yml", "r", encoding="utf-8") as f:
        content = f.read()
        assert "Database:" in content
        assert "Audit:" in content
        assert "Cloud Secrets Integration" in content
        assert "Metrics:" in content
        assert "Diagnostics:" in content

def test_cli_init_interactive_all_no(cli_runner, config_fs, mocker):
    """Проверяет интерактивный опрос в init, когда на все вопросы отвечают 'n'."""
    fs, project_root = config_fs
    answers = [
        "InteractiveProjNo", "n", "n", "n", "n", "n", "n", "n", "n", "n", "n", "n"
    ]
    mocker.patch("builtins.input", side_effect=answers)

    result = cli_runner.invoke(["init"])
    assert result.exit_code == 0
    
    assert os.path.exists("config.yml")
    assert not os.path.exists(".env")
    assert not os.path.exists("ai-lint.toml")
    assert not os.path.exists("health.py")
    assert not os.path.exists("migrations")
    assert not os.path.exists("src")

    with open("config.yml", "r", encoding="utf-8") as f:
        content = f.read()
        assert "Database:" not in content
        assert "Audit:" not in content
        assert "Metrics:" not in content
