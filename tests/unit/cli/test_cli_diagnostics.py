import json

from pydantic import BaseModel


class Settings(BaseModel):
    key: str = "val"


def test_cli_show_paths_text(cli_runner, config_fs):
    """Проверяет вывод команды show-paths в текстовом формате."""
    fs, project_root = config_fs
    result = cli_runner.invoke(["show-paths"])
    assert result.exit_code == 0
    assert "Корень проекта" in result.stdout


def test_cli_show_paths_json(cli_runner, config_fs):
    """Проверяет вывод команды show-paths в формате JSON."""
    fs, project_root = config_fs
    result = cli_runner.invoke(["show-paths", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "base_dir" in data


def test_cli_config_debug_tree(cli_runner, config_fs):
    """Проверяет команду config debug (формат tree)."""
    fs, project_root = config_fs
    fs.create_file("config.yml", contents="logging:\n  level: DEBUG")
    result = cli_runner.invoke(["config", "debug"])
    assert result.exit_code == 0
    assert "logging" in result.stdout.lower()


def test_cli_config_debug_json(cli_runner, config_fs):
    """Проверяет команду config debug (формат json)."""
    fs, project_root = config_fs
    fs.create_file("config.yml", contents="app:\n  version: 1.5")
    result = cli_runner.invoke(["config", "debug", "--format", "json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "app" in data


def _patch_template_everywhere(mocker, val=None, side_effect=None):
    """Надежное мокирование генератора в диагностических тестах."""
    targets = [
        "chutils.commands.template.generate_yaml_template",
        "src.chutils.commands.template.generate_yaml_template",
        "chutils.config.generator.generate_yaml_template"
    ]
    for t in targets:
        try:
            if side_effect:
                mocker.patch(t, side_effect=side_effect)
            else:
                mocker.patch(t, return_value=val or "key: val")
        except:
            pass


def _get_template_module():
    try:
        import chutils.commands.template as template_mod
    except ImportError:
        import src.chutils.commands.template as template_mod
    return template_mod


def test_cli_template_yaml_stdout(cli_runner, config_fs, mocker):
    """Проверяет генерацию YAML шаблона в stdout."""
    _patch_template_everywhere(mocker, val="key: val")
    template_mod = _get_template_module()
    mock_module = mocker.MagicMock()
    mock_module.Settings = Settings
    mocker.patch.object(template_mod.importlib, "import_module", return_value=mock_module)
    mocker.patch.object(template_mod, "PYDANTIC_AVAILABLE", True)

    result = cli_runner.invoke(["template", "-m", "models:Settings", "-f", "yaml"])

    assert result.exit_code == 0
    assert "key: val" in result.stdout


def test_cli_template_save_file(cli_runner, config_fs, mocker):
    """Проверяет сохранение шаблона в файл."""
    fs, project_root = config_fs
    _patch_template_everywhere(mocker, val="key: val")
    template_mod = _get_template_module()
    mock_module = mocker.MagicMock()
    mock_module.Settings = Settings
    mocker.patch.object(template_mod.importlib, "import_module", return_value=mock_module)
    mocker.patch.object(template_mod, "PYDANTIC_AVAILABLE", True)

    result = cli_runner.invoke(["template", "-m", "models:Settings", "-o", "out.yml"])

    assert result.exit_code == 0
    assert fs.exists("out.yml")
    with open("out.yml") as f:
        assert "key: val" in f.read()


def test_cli_template_no_pydantic(cli_runner, mocker):
    """Проверяет команду template без Pydantic."""
    mocker.patch("chutils.config.generator.PYDANTIC_AVAILABLE", False)
    template_mod = _get_template_module()
    mocker.patch.object(template_mod, "PYDANTIC_AVAILABLE", False)

    result = cli_runner.invoke(["template", "-m", "m:M"])
    assert result.exit_code == 1
    assert "Pydantic не установлен" in result.stdout or "Pydantic не установлен" in result.stderr


def test_cli_template_import_error(cli_runner, mocker):
    """Проверяет обработку ImportError при импорте модели."""
    mocker.patch("chutils.config.generator.PYDANTIC_AVAILABLE", True)
    template_mod = _get_template_module()
    mocker.patch.object(template_mod, "PYDANTIC_AVAILABLE", True)
    mocker.patch.object(template_mod.importlib, "import_module", side_effect=ImportError("Fail"))

    result = cli_runner.invoke(["template", "-m", "m:M"])
    assert result.exit_code == 1
    assert "Не удалось импортировать модель" in result.stdout or "Не удалось импортировать модель" in result.stderr


def test_cli_template_generation_error(cli_runner, mocker):
    """Проверяет обработку ошибки генерации."""
    _patch_template_everywhere(mocker, side_effect=Exception("Gen fail"))
    mocker.patch("chutils.config.generator.PYDANTIC_AVAILABLE", True)
    template_mod = _get_template_module()
    mock_module = mocker.MagicMock()
    mock_module.M = Settings
    mocker.patch.object(template_mod.importlib, "import_module", return_value=mock_module)
    mocker.patch.object(template_mod, "PYDANTIC_AVAILABLE", True)

    result = cli_runner.invoke(["template", "-m", "m:M"])
    assert result.exit_code == 1
    assert "Ошибка при генерации шаблона" in result.stdout or "Ошибка при генерации шаблона" in result.stderr
