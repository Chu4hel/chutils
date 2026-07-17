from chutils.dev.rules.upgrade_check import UpgradeCheckRule


def test_upgrade_check_rule_no_upgrade(mocker):
    """Проверяет, что правило ничего не возвращает, если обновления не было."""
    mocker.patch(
        "chutils.dev.rules.upgrade_check.detect_version_upgrade",
        return_value=(None, None, False)
    )

    rule = UpgradeCheckRule()
    results = rule.check("/fake/dir", [])
    assert results == []


def test_upgrade_check_rule_with_upgrade(mocker, tmp_path):
    """Проверяет поведение правила при наличии обновления версии."""
    base_dir = str(tmp_path)

    # Мокаем детекцию обновления версии: 3.1.0 -> 3.2.0
    mocker.patch(
        "chutils.dev.rules.upgrade_check.detect_version_upgrade",
        return_value=("3.1.0", "3.2.0", True)
    )

    # Мокаем сетевой клиент, возвращаем тестовые релизы
    releases = [
        {"tag_name": "v3.2.0", "body": "## Breaking Changes\n- Foo removed\n\n## New API\n- Bar added"},
    ]
    mocker.patch(
        "chutils.dev.rules.upgrade_check.fetch_changelogs",
        return_value=releases
    )

    rule = UpgradeCheckRule()
    results = rule.check(base_dir, [])

    # Должен сгенерироваться файл контекста
    context_file = tmp_path / ".chutils" / "migration_context.md"
    assert context_file.exists()

    content = context_file.read_text(encoding="utf-8")
    assert "# AI Migration Context: chutils (v3.1.0 -> v3.2.0)" in content
    assert "- Foo removed" in content
    assert "- Bar added" in content

    # Должно быть возвращено одно предупреждение
    assert len(results) == 1
    res = results[0]
    assert res.rule_name == "UpgradeCheckRule"
    assert res.severity == "warn"
    assert "v3.1.0 -> v3.2.0" in res.message
    assert "Breaking Changes: 1 шт." in res.message
    assert "New API: 1 шт." in res.message
    assert res.file_path == str(tmp_path / "pyproject.toml")
