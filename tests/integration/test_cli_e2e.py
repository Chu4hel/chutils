import subprocess
import sys


def test_cli_help_e2e():
    """Проверяет вызов справки через subprocess (entrypoint check)."""
    # Используем sys.executable -m chutils если chutils не установлен в venv, 
    # но обычно в dev окружении он доступен как команда.
    # Для надежности в тестах часто используют вызов модуля.
    result = subprocess.run(
        [sys.executable, "-m", "chutils", "--help"],
        capture_output=True,
        text=True,
        check=True
    )

    assert result.returncode == 0
    assert "chutils" in result.stdout
    assert "Доступные команды" in result.stdout


def test_cli_diagnostics_e2e():
    """Проверяет вызов diagnostics через subprocess."""
    result = subprocess.run(
        [sys.executable, "-m", "chutils", "show-paths", "--json"],
        capture_output=True,
        text=True,
        check=True
    )

    assert result.returncode == 0
    # Проверяем, что вывод - валидный JSON
    import json
    data = json.loads(result.stdout)
    assert "base_dir" in data
