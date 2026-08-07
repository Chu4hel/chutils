"""Тесты scaffolding команд и распаковки шаблонов chutils init --template."""

from pathlib import Path

from chutils.scaffold import unpack_template


def test_unpack_vk_miniapp_template(tmp_path: Path):
    target = tmp_path / "my_vk_app"
    files = unpack_template("vk-miniapp", target, context={"project_name": "MyVKApp"})

    assert len(files) > 0
    main_py = target / "backend" / "main.py"
    assert main_py.exists()
    content = main_py.read_text(encoding="utf-8")
    assert "MyVKApp Backend" in content
    assert "VKMAAuthMiddleware" in content


def test_unpack_nonexistent_template(tmp_path: Path):
    target = tmp_path / "empty_app"
    files = unpack_template("unknown_template", target)
    assert files == []
