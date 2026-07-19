from unittest.mock import MagicMock

import pytest

from chutils.exceptions import ChutilsException


def test_install_hooks_no_git(tmp_path, monkeypatch) -> None:
    """Проверяет выброс ChutilsException, если директория .git не найдена."""
    from chutils.commands.dev import DevCommand

    # Подменяем os.getcwd, чтобы он возвращал нашу временную папку без .git
    monkeypatch.setattr("os.getcwd", lambda: str(tmp_path))

    cmd = DevCommand()
    args = MagicMock()
    args.force = False

    with pytest.raises(ChutilsException) as exc_info:
        cmd.handle_install_hooks(args)

    assert "не найдена" in str(exc_info.value)


def test_install_hooks_new_file(tmp_path, monkeypatch) -> None:
    """Проверяет создание нового файла хука pre-commit."""
    from chutils.commands.dev import DevCommand

    # Создаем фиктивную папку .git
    git_dir = tmp_path / ".git"
    git_dir.mkdir()

    monkeypatch.setattr("os.getcwd", lambda: str(tmp_path))

    cmd = DevCommand()
    args = MagicMock()
    args.force = False

    cmd.handle_install_hooks(args)

    hook_path = git_dir / "hooks" / "pre-commit"
    assert hook_path.exists()

    content = hook_path.read_text(encoding="utf-8")
    assert "# chutils pre-commit hook" in content
    assert "chutils dev ai-lint" in content


def test_install_hooks_append_existing(tmp_path, monkeypatch) -> None:
    """Проверяет безопасное добавление в существующий файл хука."""
    from chutils.commands.dev import DevCommand

    git_dir = tmp_path / ".git"
    hooks_dir = git_dir / "hooks"
    hooks_dir.mkdir(parents=True)

    hook_path = hooks_dir / "pre-commit"
    hook_path.write_text("echo 'hello'", encoding="utf-8")

    monkeypatch.setattr("os.getcwd", lambda: str(tmp_path))

    cmd = DevCommand()
    args = MagicMock()
    args.force = False

    cmd.handle_install_hooks(args)

    content = hook_path.read_text(encoding="utf-8")
    assert "echo 'hello'" in content
    assert "# === CHUTILS HOOK START ===" in content
    assert "chutils dev ai-lint" in content


def test_install_hooks_force_overwrite(tmp_path, monkeypatch) -> None:
    """Проверяет перезапись хука с флагом --force."""
    from chutils.commands.dev import DevCommand

    git_dir = tmp_path / ".git"
    hooks_dir = git_dir / "hooks"
    hooks_dir.mkdir(parents=True)

    hook_path = hooks_dir / "pre-commit"
    hook_path.write_text("echo 'hello'", encoding="utf-8")

    monkeypatch.setattr("os.getcwd", lambda: str(tmp_path))

    cmd = DevCommand()
    args = MagicMock()
    args.force = True

    cmd.handle_install_hooks(args)

    content = hook_path.read_text(encoding="utf-8")
    assert "echo 'hello'" not in content
    assert "# chutils pre-commit hook" in content


def test_install_hooks_with_ruff_and_flake8(tmp_path, monkeypatch) -> None:
    """Проверяет создание pre-commit хука с дополнительными проверками ruff и flake8."""
    from chutils.commands.dev import DevCommand

    git_dir = tmp_path / ".git"
    git_dir.mkdir()

    monkeypatch.setattr("os.getcwd", lambda: str(tmp_path))

    cmd = DevCommand()
    args = MagicMock()
    args.force = False
    args.ruff = True
    args.flake8 = True

    cmd.handle_install_hooks(args)

    hook_path = git_dir / "hooks" / "pre-commit"
    assert hook_path.exists()

    content = hook_path.read_text(encoding="utf-8")
    # ruff и flake8 должны работать только по staged файлам, а не по всему проекту
    assert "CHUTILS_STAGED_PY" in content          # сбор staged .py файлов
    assert "xargs" in content                       # передача файлов через xargs
    assert "ruff check --fix" in content            # ruff есть в хуке
    assert "xargs" in content and "flake8" in content  # flake8 есть в хуке
    assert "flake8 ." not in content               # не должно сканировать весь проект
