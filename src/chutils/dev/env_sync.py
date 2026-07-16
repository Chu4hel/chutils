"""
Ядро логики сравнения и синхронизации .env и .env.example.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from chutils.dev.env_parser import (
    merge_env_structures,
    parse_env_file,
    write_env_file,
)


@dataclass
class EnvDiff:
    """Представляет расхождения в ключах между .env и .env.example."""
    missing_in_env: list[str]
    missing_in_example: list[str]

    def has_diff(self) -> bool:
        """Проверяет, есть ли расхождения в ключах.

        Returns:
            True, если расхождения есть, иначе False.
        """
        return bool(self.missing_in_env or self.missing_in_example)


def check_env_sync(env_path: str | Path, example_path: str | Path) -> EnvDiff:
    """Сравнивает наборы ключей в .env и .env.example.

    Args:
        env_path: Путь к файлу .env.
        example_path: Путь к файлу .env.example.

    Returns:
        Объект EnvDiff, содержащий списки отсутствующих ключей.
    """
    env_entries = parse_env_file(env_path)
    example_entries = parse_env_file(example_path)

    env_keys = {e.key for e in env_entries if e.key is not None}
    example_keys = {e.key for e in example_entries if e.key is not None}

    missing_in_env = sorted(list(example_keys - env_keys))
    missing_in_example = sorted(list(env_keys - example_keys))

    return EnvDiff(
        missing_in_env=missing_in_env,
        missing_in_example=missing_in_example,
    )


def sync_env_files(
        env_path: str | Path,
        example_path: str | Path,
        sync_env: bool = True,
        sync_example: bool = True,
) -> tuple[bool, bool]:
    """Синхронизирует файлы .env и .env.example.

    Переносит отсутствующие ключи с сохранением комментариев. При обновлении
    .env.example значения сбрасываются. При обновлении .env значения по умолчанию
    из .env.example сохраняются.

    Args:
        env_path: Путь к файлу .env.
        example_path: Путь к файлу .env.example.
        sync_env: Выполнить ли синхронизацию .env (добавить ключи из .env.example).
        sync_example: Выполнить ли синхронизацию .env.example (добавить ключи из .env).

    Returns:
        Кортеж (env_updated, example_updated), где каждый элемент равен True,
        если соответствующий файл был изменен.
    """
    env_updated = False
    example_updated = False

    env_entries = parse_env_file(env_path)
    example_entries = parse_env_file(example_path)

    env_keys = {e.key for e in env_entries if e.key is not None}
    example_keys = {e.key for e in example_entries if e.key is not None}

    # Синхронизируем .env (добавляем из .env.example)
    if sync_env:
        missing_in_env = example_keys - env_keys
        if missing_in_env:
            # Сливаем example в env, сохраняя значения по умолчанию (empty_values=False)
            new_env_entries = merge_env_structures(
                source_entries=example_entries,
                target_entries=env_entries,
                empty_values=False,
            )
            write_env_file(env_path, new_env_entries)
            env_updated = True

    # Синхронизируем .env.example (добавляем из .env)
    if sync_example:
        missing_in_example = env_keys - example_keys
        if missing_in_example:
            # Сливаем env в example, обнуляя значения (empty_values=True)
            new_example_entries = merge_env_structures(
                source_entries=env_entries,
                target_entries=example_entries,
                empty_values=True,
            )
            write_env_file(example_path, new_example_entries)
            example_updated = True

    return env_updated, example_updated
