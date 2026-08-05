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

    mocker.patch(
        "chutils.dev.rules.upgrade_check.detect_version_upgrade",
        return_value=("3.1.0", "3.2.0", True)
    )

    releases = [
        {"tag_name": "v3.2.0", "body": "## Breaking Changes\n- Foo removed\n\n## New API\n- Bar added"},
    ]
    mocker.patch(
        "chutils.dev.rules.upgrade_check.fetch_changelogs",
        return_value=releases
    )

    rule = UpgradeCheckRule()
    results = rule.check(base_dir, [])

    context_file = tmp_path / ".chutils" / "migration_context.md"
    assert context_file.exists()

    content = context_file.read_text(encoding="utf-8")
    assert "# AI Migration Context: chutils (v3.1.0 -> v3.2.0)" in content
    assert "- Foo removed" in content
    assert "- Bar added" in content

    assert len(results) == 1
    res = results[0]
    assert res.rule_name == "UpgradeCheckRule"
    assert res.severity == "warn"
    assert "v3.1.0 -> v3.2.0" in res.message


def test_upgrade_check_rule_disabled_via_env(mocker, monkeypatch, tmp_path):
    """Проверяет отключение правила через CHUTILS_DISABLE_UPGRADE_CHECK=1."""
    monkeypatch.setenv("CHUTILS_DISABLE_UPGRADE_CHECK", "1")
    mocker.patch(
        "chutils.dev.rules.upgrade_check.detect_version_upgrade",
        return_value=("3.1.0", "3.2.0", True)
    )

    rule = UpgradeCheckRule()
    results = rule.check(str(tmp_path), [])

    assert results == []
    context_file = tmp_path / ".chutils" / "migration_context.md"
    assert not context_file.exists()


def test_upgrade_check_rule_no_changelog_via_env(mocker, monkeypatch, tmp_path):
    """Проверяет отключение создания файла migration_context.md через CHUTILS_GENERATE_CHANGELOG=0."""
    monkeypatch.setenv("CHUTILS_GENERATE_CHANGELOG", "0")
    mocker.patch(
        "chutils.dev.rules.upgrade_check.detect_version_upgrade",
        return_value=("3.1.0", "3.2.0", True)
    )
    mocker.patch(
        "chutils.dev.rules.upgrade_check.fetch_changelogs",
        return_value=[{"tag_name": "v3.2.0", "body": "## New API\n- Bar"}]
    )

    rule = UpgradeCheckRule()
    results = rule.check(str(tmp_path), [])

    context_file = tmp_path / ".chutils" / "migration_context.md"
    assert not context_file.exists()
    assert len(results) == 1


def test_upgrade_check_rule_disabled_via_config(mocker, tmp_path):
    """Проверяет отключение правила через конфиг ai-lint.toml (exclude_rules)."""
    mocker.patch(
        "chutils.dev.rules.upgrade_check.detect_version_upgrade",
        return_value=("3.1.0", "3.2.0", True)
    )
    mocker.patch(
        "chutils.config.dev.load_ai_lint_config",
        return_value={"exclude_rules": ["UpgradeCheckRule"]}
    )

    rule = UpgradeCheckRule()
    results = rule.check(str(tmp_path), [])

    assert results == []
