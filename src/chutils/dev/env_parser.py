"""
Модуль для парсинга, сохранения и слияния файлов конфигурации окружения (.env и .env.example).
Сохраняет форматирование, пустые строки и комментарии.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class EnvEntry:
    """Представляет отдельную строку в env-файле."""
    raw_line: str
    key: str | None = None
    value: str | None = None
    comment: str | None = None
    is_comment: bool = False
    is_empty: bool = False


def parse_env_line(line: str) -> EnvEntry:
    """Парсит одну строку env-файла и возвращает объект EnvEntry.

    Поддерживает:
    - Пустые строки
    - Строки комментариев (# comment)
    - Переменные окружения вида KEY=VALUE, KEY="VALUE", KEY='VALUE'
    - Инлайн-комментарии к переменным

    Args:
        line: Исходная строка файла.

    Returns:
        Объект EnvEntry, содержащий распарсенную информацию.
    """
    line_strip = line.strip()
    if not line_strip:
        return EnvEntry(raw_line=line, is_empty=True)
    if line_strip.startswith("#"):
        comment_text = line_strip[1:].strip()
        return EnvEntry(raw_line=line, is_comment=True, comment=comment_text)

    # Ищем переменную окружения
    match = re.match(r"^\s*([A-Za-z0-9_.-]+)\s*=\s*(.*)$", line)
    if not match:
        return EnvEntry(raw_line=line)

    key = match.group(1)
    raw_val = match.group(2).strip()

    value = ""
    comment = None

    if raw_val.startswith('"'):
        # Ищем закрывающую двойную кавычку
        val_match = re.match(r'^"([^"\\]*(?:\\.[^"\\]*)*)"(?:\s*#\s*(.*))?$', raw_val)
        if val_match:
            value = val_match.group(1)
            comment = val_match.group(2)
        else:
            value = raw_val
    elif raw_val.startswith("'"):
        # Ищем закрывающую одинарную кавычку
        val_match = re.match(r"^'([^'\\]*(?:\\.[^'\\]*)*)'(?:\s*#\s*(.*))?$", raw_val)
        if val_match:
            value = val_match.group(1)
            comment = val_match.group(2)
        else:
            value = raw_val
    else:
        # Значение без кавычек, комментарий может быть отделен знаком '#'
        if "#" in raw_val:
            parts = raw_val.split("#", 1)
            value = parts[0].strip()
            comment = parts[1].strip()
        else:
            value = raw_val

    return EnvEntry(
        raw_line=line,
        key=key,
        value=value,
        comment=comment,
    )


def parse_env_file(path: str | Path) -> list[EnvEntry]:
    """Читает env-файл и возвращает список структур EnvEntry.

    Args:
        path: Путь к файлу конфигурации.

    Returns:
        Список записей EnvEntry.
    """
    p = Path(path)
    if not p.exists():
        return []

    entries: list[EnvEntry] = []
    with open(p, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            entries.append(parse_env_line(line))
    return entries


def write_env_file(path: str | Path, entries: list[EnvEntry]) -> None:
    """Записывает структуру EnvEntry обратно в файл, сохраняя оригинальный вид.

    Args:
        path: Путь для сохранения файла.
        entries: Список сохраняемых записей EnvEntry.
    """
    from chutils.fs import ensure_dir, atomic_write
    p = Path(path)
    ensure_dir(p.parent)

    lines: list[str] = []
    for entry in entries:
        if entry.key is not None:
            # Если запись соответствует переменной окружения
            val_str = entry.value if entry.value is not None else ""
            # Если значение содержит пробелы или кавычки, проверим
            # Для пустых значений кавычки опускаем.
            # Для непустых значений, если исходная строка raw_line распарсивается
            # в те же самые значения, выводим её без изменений для сохранения кавычек.
            parsed_raw = parse_env_line(entry.raw_line)
            if (
                    parsed_raw.key == entry.key
                    and parsed_raw.value == entry.value
                    and parsed_raw.comment == entry.comment
            ):
                lines.append(entry.raw_line)
            else:
                # Рендерим новую строку
                line_to_write = f"{entry.key}={val_str}"
                if entry.comment is not None:
                    line_to_write += f" # {entry.comment}"
                line_to_write += "\n"
                lines.append(line_to_write)
        else:
            line_to_write = entry.raw_line
            if not line_to_write.endswith("\n"):
                line_to_write += "\n"
            lines.append(line_to_write)

    atomic_write(p, "".join(lines))


def merge_env_structures(
        source_entries: list[EnvEntry],
        target_entries: list[EnvEntry],
        empty_values: bool = False,
) -> list[EnvEntry]:
    """Сливает две структуры env-файлов.

    Находит новые ключи в source_entries, которых нет в target_entries,
    и добавляет их в конец target_entries с сохранением связанных комментариев.

    Args:
        source_entries: Список записей из исходного файла (источник).
        target_entries: Список записей из целевого файла (приемник).
        empty_values: Если True, новые ключи будут перенесены с пустым значением.

    Returns:
        Новый список записей EnvEntry, содержащий объединенную структуру.
    """
    target_keys = {e.key for e in target_entries if e.key is not None}
    new_entries = list(target_entries)

    # Индексируем source для поиска комментариев
    source_keys_indices: dict[str, int] = {}
    for idx, entry in enumerate(source_entries):
        if entry.key is not None:
            source_keys_indices[entry.key] = idx

    keys_to_add: list[str] = []
    for entry in source_entries:
        if entry.key is not None and entry.key not in target_keys:
            keys_to_add.append(entry.key)

    if not keys_to_add:
        return new_entries

    # Добавляем пустую строку-разделитель в конец целевого списка,
    # если он не пуст и последняя строка не пустая
    if new_entries and not new_entries[-1].is_empty:
        new_entries.append(EnvEntry(raw_line="\n", is_empty=True))

    for key in keys_to_add:
        idx = source_keys_indices[key]
        entry = source_entries[idx]

        # Ищем комментарии перед ключом в исходном файле
        comments_before: list[EnvEntry] = []
        comment_idx = idx - 1
        while comment_idx >= 0:
            prev_entry = source_entries[comment_idx]
            if prev_entry.is_comment:
                comments_before.insert(0, prev_entry)
                comment_idx -= 1
            else:
                break

        # Вставляем собранные комментарии
        for c in comments_before:
            raw_c = c.raw_line if c.raw_line.endswith("\n") else c.raw_line + "\n"
            new_entries.append(EnvEntry(raw_line=raw_c, is_comment=True, comment=c.comment))

        # Создаем новую запись для ключа
        val = "" if empty_values else (entry.value if entry.value is not None else "")
        # Формируем сырую строку для нового ключа
        raw_key_line = f"{key}={val}"
        if entry.comment is not None:
            raw_key_line += f" # {entry.comment}"
        raw_key_line += "\n"

        new_entries.append(EnvEntry(
            raw_line=raw_key_line,
            key=key,
            value=val,
            comment=entry.comment,
        ))

    return new_entries
