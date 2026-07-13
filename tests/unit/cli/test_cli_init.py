import os
import sys


def test_cli_init_success(cli_runner, config_fs):
    """Проверяет успешную инициализацию проекта с дефолтными настройками."""
    fs, project_root = config_fs
    result = cli_runner.invoke(["init", "-y"])
    assert result.exit_code == 0
    assert "config.yml" in result.stdout
    assert os.path.exists("config.yml")


def test_cli_init_custom_name(cli_runner, config_fs, mocker):
    """Проверяет инициализацию с кастомным именем проекта через input."""
    fs, project_root = config_fs
    mocker.patch("builtins.input", return_value="MyCoolProject")
    result = cli_runner.invoke(["init"])
    assert result.exit_code == 0
    with open("config.yml") as f:
        assert "MyCoolProject" in f.read()


def test_cli_init_already_exists_skip(cli_runner, config_fs, mocker):
    """Проверяет пропуск создания config.yml, если он уже существует."""
    fs, project_root = config_fs
    fs.create_file("config.yml", contents="existing content")
    mocker.patch("builtins.input", side_effect=["Project", "n"])
    result = cli_runner.invoke(["init"])
    assert "отменено" in result.stdout
    with open("config.yml") as f:
        assert f.read() == "existing content"


def test_cli_init_model_no_pydantic(cli_runner, config_fs, mocker):
    """Проверяет инициализацию с моделью без Pydantic."""
    fs, project_root = config_fs

    # Патчим PYDANTIC_AVAILABLE в генераторе
    mocker.patch("chutils.config.generator.PYDANTIC_AVAILABLE", False)
    # И на случай если он уже импортирован в init
    for mod in ["chutils.commands.init", "src.chutils.commands.init"]:
        if mod in sys.modules:
            mocker.patch(f"{mod}.PYDANTIC_AVAILABLE", False, create=True)

    result = cli_runner.invoke(["init", "-y", "-m", "m:M"])
    assert result.exit_code == 0
    assert "Pydantic не установлен" in result.stdout


def test_cli_init_gitignore_already_contains(cli_runner, config_fs):
    """Проверяет пропуск обновления .gitignore, если записи уже есть."""
    fs, project_root = config_fs
    # Список в коде init.py
    entries = [
        "config.local.yml", "config.local.yaml", "config.local.ini", "config.local.json",
        "*.log", "logs/"
    ]
    contents = "\n".join(entries) + "\n"
    fs.create_file(".gitignore", contents=contents)

    result = cli_runner.invoke(["init", "-y"])
    assert result.exit_code == 0
    assert "уже содержит необходимые исключения" in result.stdout


def test_cli_init_with_model_success(cli_runner, config_fs, mocker):
    """Проверяет успешную генерацию на основе модели."""
    fs, project_root = config_fs
    from pydantic import BaseModel
    class Settings(BaseModel):
        api_key: str = "default_key"

    # Патчим генератор ВЕЗДЕ
    targets = [
        "chutils.config.generator.generate_yaml_template",
        "chutils.commands.init.generate_yaml_template",
        "src.chutils.commands.init.generate_yaml_template"
    ]
    for t in targets:
        try:
            mocker.patch(t, return_value="api_key: default_key")
        except:
            pass

    mocker.patch("chutils.config.generator.PYDANTIC_AVAILABLE", True)

    # Создаём mock-модуль с нужным атрибутом Settings на нём —
    # это безопасная альтернатива патчу builtins.getattr
    mock_module = mocker.MagicMock()
    mock_module.Settings = Settings
    mocker.patch("importlib.import_module", return_value=mock_module)

    result = cli_runner.invoke(["init", "-y", "-m", "myapp:Settings"])
    assert result.exit_code == 0
    with open("config.yml") as f:
        content = f.read()
        assert "api_key: default_key" in content

