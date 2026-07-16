from __future__ import annotations

from pathlib import Path

from chutils.dev.env_sync import check_env_sync, sync_env_files


def test_check_env_sync(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    example_file = tmp_path / ".env.example"

    env_file.write_text("A=1\nB=2\n", encoding="utf-8")
    example_file.write_text("A=10\nC=30\n", encoding="utf-8")

    diff = check_env_sync(env_file, example_file)
    assert diff.has_diff()
    assert diff.missing_in_env == ["C"]
    assert diff.missing_in_example == ["B"]


def test_sync_env_files(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    example_file = tmp_path / ".env.example"

    env_file.write_text("A=1\nB=2\n", encoding="utf-8")
    example_file.write_text("A=10\nC=30\n", encoding="utf-8")

    # Синхронизируем оба файла
    env_updated, example_updated = sync_env_files(
        env_path=env_file,
        example_path=example_file,
        sync_env=True,
        sync_example=True,
    )

    assert env_updated
    assert example_updated

    # Проверяем содержимое .env
    env_content = env_file.read_text(encoding="utf-8")
    assert "A=1\n" in env_content
    assert "B=2\n" in env_content
    assert "C=30\n" in env_content  # C перенесено со значением по умолчанию

    # Проверяем содержимое .env.example
    example_content = example_file.read_text(encoding="utf-8")
    assert "A=10\n" in example_content
    assert "C=30\n" in example_content
    assert "B=\n" in example_content  # B перенесено с пустым значением
