import os


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
    with open("config.yml", "r") as f:
        assert "MyCoolProject" in f.read()


def test_cli_init_already_exists_skip(cli_runner, config_fs, mocker):
    """Проверяет пропуск создания config.yml, если он уже существует."""
    fs, project_root = config_fs
    fs.create_file("config.yml", contents="existing content")
    mocker.patch("builtins.input", side_effect=["Project", "n"])
    result = cli_runner.invoke(["init"])
    assert "отменено" in result.stdout
    with open("config.yml", "r") as f:
        assert f.read() == "existing content"


def test_cli_init_with_model(cli_runner, config_fs, mocker):
    """Проверяет генерацию конфига на основе Pydantic модели с надежным мокированием."""
    fs, project_root = config_fs
    from pydantic import BaseModel
    class Settings(BaseModel):
        api_key: str = "default_key"

    # Патчим в источнике (оба варианта путей)
    for path in ["chutils.config.generator", "src.chutils.config.generator"]:
        try:
            mocker.patch(f"{path}.PYDANTIC_AVAILABLE", True)
            mocker.patch(f"{path}.generate_yaml_template", return_value="api_key: default_key")
        except ImportError:
            pass

    mocker.patch("importlib.import_module")
    mocker.patch("builtins.getattr", return_value=Settings)

    result = cli_runner.invoke(["init", "-y", "-m", "myapp_config:Settings"])

    assert result.exit_code == 0
    with open("config.yml", "r") as f:
        assert "api_key: default_key" in f.read()
