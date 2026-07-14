from __future__ import annotations

from pathlib import Path

from chutils.dev.env_parser import (
    merge_env_structures,
    parse_env_file,
    parse_env_line,
    write_env_file,
)


def test_parse_env_line_empty_and_comments() -> None:
    # Пустая строка
    e1 = parse_env_line("   \n")
    assert e1.is_empty
    assert e1.key is None

    # Комментарий
    e2 = parse_env_line("# Это комментарий  \n")
    assert e2.is_comment
    assert e2.comment == "Это комментарий"
    assert e2.key is None


def test_parse_env_line_variables() -> None:
    # Обычное значение без кавычек
    e1 = parse_env_line("DB_PORT=5432\n")
    assert e1.key == "DB_PORT"
    assert e1.value == "5432"
    assert e1.comment is None

    # Значение в двойных кавычках
    e2 = parse_env_line('SECRET_KEY="super-secret-123"\n')
    assert e2.key == "SECRET_KEY"
    assert e2.value == "super-secret-123"
    assert e2.comment is None

    # Значение в одинарных кавычках
    e3 = parse_env_line("APP_ENV='production'\n")
    assert e3.key == "APP_ENV"
    assert e3.value == "production"
    assert e3.comment is None

    # Ключ со спецсимволами
    e4 = parse_env_line("my.app-name_1 = value\n")
    assert e4.key == "my.app-name_1"
    assert e4.value == "value"


def test_parse_env_line_inline_comments() -> None:
    # Инлайн комментарий без кавычек
    e1 = parse_env_line("DEBUG=True # Включить отладку\n")
    assert e1.key == "DEBUG"
    assert e1.value == "True"
    assert e1.comment == "Включить отладку"

    # Инлайн комментарий с двойными кавычками
    e2 = parse_env_line('API_URL="https://api.example.com" # Продовый API\n')
    assert e2.key == "API_URL"
    assert e2.value == "https://api.example.com"
    assert e2.comment == "Продовый API"

    # Символ решетки внутри кавычек
    e3 = parse_env_line('HASH_SALT="abc#123"\n')
    assert e3.key == "HASH_SALT"
    assert e3.value == "abc#123"
    assert e3.comment is None

    # Символ решетки внутри кавычек и комментарий после
    e4 = parse_env_line('HASH_SALT="abc#123" # соль для хэша\n')
    assert e4.key == "HASH_SALT"
    assert e4.value == "abc#123"
    assert e4.comment == "соль для хэша"


def test_parse_and_write_env_file(tmp_path: Path) -> None:
    file_content = (
        "# Общие настройки\n"
        "APP_NAME=MyApp\n"
        "\n"
        "# Настройки базы\n"
        "DB_HOST=localhost\n"
        "DB_PASS=\"pass#word\" # пароль от бд\n"
    )
    env_file = tmp_path / ".env"
    env_file.write_text(file_content, encoding="utf-8")

    # Чтение
    entries = parse_env_file(env_file)
    assert len(entries) == 6
    assert entries[0].is_comment
    assert entries[1].key == "APP_NAME"
    assert entries[2].is_empty
    assert entries[3].is_comment
    assert entries[4].key == "DB_HOST"
    assert entries[5].key == "DB_PASS"
    assert entries[5].comment == "пароль от бд"

    # Запись без изменений
    out_file = tmp_path / ".env.out"
    write_env_file(out_file, entries)
    assert out_file.read_text(encoding="utf-8") == file_content

    # Запись с изменениями
    entries[4].value = "127.0.0.1"
    write_env_file(out_file, entries)
    new_content = out_file.read_text(encoding="utf-8")
    assert "DB_HOST=127.0.0.1\n" in new_content


def test_merge_env_structures() -> None:
    source_content = (
        "# Заголовок\n"
        "A=1\n"
        "\n"
        "# Комментарий к B\n"
        "B=2 # инлайн B\n"
        "C=3\n"
    )
    target_content = (
        "A=10\n"
    )

    source_entries = [parse_env_line(line) for line in source_content.splitlines(keepends=True)]
    target_entries = [parse_env_line(line) for line in target_content.splitlines(keepends=True)]

    # Слияние с обнулением значений (empty_values=True)
    merged_empty = merge_env_structures(source_entries, target_entries, empty_values=True)
    # Ключи B и C должны быть добавлены. B должен перенести свои комментарии.
    keys = [e.key for e in merged_empty if e.key is not None]
    assert keys == ["A", "B", "C"]

    # Проверим, что A сохранило значение 10
    a_entry = [e for e in merged_empty if e.key == "A"][0]
    assert a_entry.value == "10"

    # Проверим, что B имеет пустое значение, но комментарии перенесены
    b_entry = [e for e in merged_empty if e.key == "B"][0]
    assert b_entry.value == ""
    assert b_entry.comment == "инлайн B"

    # Проверим наличие предыдущих комментариев для B в объединенном списке
    b_idx = merged_empty.index(b_entry)
    prev_entry = merged_empty[b_idx - 1]
    assert prev_entry.is_comment
    assert prev_entry.comment == "Комментарий к B"

    # Слияние без обнуления значений (empty_values=False)
    merged_full = merge_env_structures(source_entries, target_entries, empty_values=False)
    b_full_entry = [e for e in merged_full if e.key == "B"][0]
    assert b_full_entry.value == "2"
