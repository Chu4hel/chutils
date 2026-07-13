import subprocess
from unittest.mock import patch

import pytest

from chutils.cli import main


def test_hooks_integration_git_repo(tmp_path, monkeypatch) -> None:
    """Интеграционный тест: инициализация репозитория Git и успешная установка хука через CLI."""
    # 1. Инициализируем временный Git-репозиторий
    try:
        subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True, check=True)
    except Exception:
        pytest.skip("Git не установлен в системе, пропускаем интеграционный тест")

    monkeypatch.setattr("os.getcwd", lambda: str(tmp_path))

    # 2. Вызываем main() с аргументами dev install-hooks
    with patch("sys.argv", ["chutils", "dev", "install-hooks"]):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0

    # Проверяем, что файл хука создан
    hook_path = tmp_path / ".git" / "hooks" / "pre-commit"
    assert hook_path.exists()

    content = hook_path.read_text(encoding="utf-8")
    assert "chutils dev ai-lint" in content


def test_hooks_integration_no_git_repo(tmp_path, monkeypatch) -> None:
    """Интеграционный тест: вызов команды в директории без Git-репозитория."""
    monkeypatch.setattr("os.getcwd", lambda: str(tmp_path))

    with patch("sys.argv", ["chutils", "dev", "install-hooks"]):
        with pytest.raises(SystemExit) as exc_info:
            main()
        # Должен быть выход с ошибкой (exit code 1)
        assert exc_info.value.code == 1
