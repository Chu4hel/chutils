import json


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


def test_cli_template_yaml_stdout(cli_runner, config_fs, mocker):
    """Проверяет генерацию YAML шаблона с агрессивным мокированием."""
    fs, project_root = config_fs
    from pydantic import BaseModel
    class Settings(BaseModel):
        key: str = "val"

    # Патчим везде, где функция могла осесть
    targets = [
        "chutils.commands.template.generate_yaml_template",
        "src.chutils.commands.template.generate_yaml_template",
        "chutils.config.generator.generate_yaml_template",
        "src.chutils.config.generator.generate_yaml_template"
    ]
    for target in targets:
        try:
            mocker.patch(target, return_value="key: val")
        except (ImportError, AttributeError):
            pass

    mocker.patch("chutils.commands.template.importlib.import_module")
    mocker.patch("chutils.commands.template.getattr", return_value=Settings)
    mocker.patch("chutils.commands.template.PYDANTIC_AVAILABLE", True)

    result = cli_runner.invoke(["template", "-m", "models:Settings", "-f", "yaml"])

    assert result.exit_code == 0
    assert "key: val" in result.stdout


def test_cli_template_save_file(cli_runner, config_fs, mocker):
    """Проверяет сохранение шаблона в файл с агрессивным мокированием."""
    fs, project_root = config_fs
    from pydantic import BaseModel
    class Settings(BaseModel):
        key: str = "val"

    targets = [
        "chutils.commands.template.generate_yaml_template",
        "src.chutils.commands.template.generate_yaml_template",
        "chutils.config.generator.generate_yaml_template",
        "src.chutils.config.generator.generate_yaml_template"
    ]
    for target in targets:
        try:
            mocker.patch(target, return_value="key: val")
        except (ImportError, AttributeError):
            pass

    mocker.patch("chutils.commands.template.importlib.import_module")
    mocker.patch("chutils.commands.template.getattr", return_value=Settings)
    mocker.patch("chutils.commands.template.PYDANTIC_AVAILABLE", True)

    result = cli_runner.invoke(["template", "-m", "models:Settings", "-o", "out.yml"])

    assert result.exit_code == 0
    assert fs.exists("out.yml")
    with open("out.yml", "r") as f:
        assert "key: val" in f.read()
