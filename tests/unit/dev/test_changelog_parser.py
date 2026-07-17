from chutils.dev.changelog_parser import (
    parse_release_body,
    filter_releases_by_version_range,
    generate_migration_context_markdown,
)


def test_parse_release_body_english():
    """Проверяет парсинг англоязычного описания релиза."""
    body = """
## Breaking Changes
- Removed old deprecated function foo()
- Config key format has changed

## New API
* Added new method bar()
* New decorator @cache_with_tags is now available

## Deprecations
1. Method baz() is deprecated and will be removed in 4.0
"""
    result = parse_release_body(body)
    assert result["breaking_changes"] == [
        "Removed old deprecated function foo()",
        "Config key format has changed",
    ]
    assert result["new_api"] == [
        "Added new method bar()",
        "New decorator @cache_with_tags is now available",
    ]
    assert result["deprecations"] == [
        "Method baz() is deprecated and will be removed in 4.0",
    ]


def test_parse_release_body_russian():
    """Проверяет парсинг русскоязычного описания релиза."""
    body = """
### Критические изменения:
- Удалена старая функция foo()

### Новые функции:
- Добавлен метод bar()

### Устаревшие возможности:
- Метод baz() объявлен устаревшим
"""
    result = parse_release_body(body)
    assert result["breaking_changes"] == ["Удалена старая функция foo()"]
    assert result["new_api"] == ["Добавлен метод bar()"]
    assert result["deprecations"] == ["Метод baz() объявлен устаревшим"]


def test_parse_release_body_empty():
    """Проверяет поведение при пустом описании."""
    result = parse_release_body("")
    assert result == {
        "breaking_changes": [],
        "new_api": [],
        "deprecations": [],
    }


def test_filter_releases_by_version_range():
    """Проверяет фильтрацию релизов по диапазону версий."""
    releases = [
        {"tag_name": "v3.1.0", "body": "Release 3.1.0"},
        {"tag_name": "v3.2.0-rc1", "body": "Release 3.2.0-rc1"},
        {"tag_name": "v3.2.0", "body": "Release 3.2.0"},
        {"tag_name": "v3.0.0", "body": "Release 3.0.0"},
    ]

    # С диапазоном (3.0.0, 3.2.0] должны остаться 3.1.0, 3.2.0-rc1, 3.2.0
    # Отсортированные по возрастанию
    filtered = filter_releases_by_version_range(releases, "3.0.0", "3.2.0")
    tags = [r["tag_name"] for r in filtered]
    assert tags == ["v3.1.0", "v3.2.0-rc1", "v3.2.0"]


def test_generate_migration_context_markdown():
    """Проверяет генерацию Markdown контекста."""
    parsed = {
        "breaking_changes": ["Change 1"],
        "new_api": [],
        "deprecations": ["Deprecation 1"],
    }
    markdown = generate_migration_context_markdown(parsed, "3.0.0", "3.1.0")

    assert "# AI Migration Context: chutils (v3.0.0 -> v3.1.0)" in markdown
    assert "## Breaking Changes" in markdown
    assert "- Change 1" in markdown
    assert "## New API" in markdown
    assert "- *Нет изменений в этой категории.*" in markdown
    assert "## Deprecations" in markdown
    assert "- Deprecation 1" in markdown
