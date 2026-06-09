from unittest import mock

from pydantic import BaseModel


class Settings(BaseModel):
    app_name: str
    version: float


def test_cli_validate_success(cli_runner, config_fs, mocker):
    """Проверяет успешную валидацию конфига."""
    fs, project_root = config_fs
    fs.create_file("config.yml", contents="app_name: MyApp\nversion: 2.0")

    mocker.patch("chutils.commands.validate._import_string", return_value=Settings)

    result = cli_runner.invoke(["validate", "-m", "any:Settings"])

    assert result.exit_code == 0
    assert "успешно прошла валидацию" in result.stdout


def test_cli_validate_fail_validation(cli_runner, config_fs, mocker):
    """Проверяет поведение при ошибке валидации."""
    fs, project_root = config_fs
    fs.create_file("config.yml", contents="app_name: MyApp\nversion: not-a-number")

    mocker.patch("chutils.commands.validate._import_string", return_value=Settings)

    result = cli_runner.invoke(["validate", "-m", "any:Settings"])

    assert result.exit_code == 1
    assert "version" in result.stdout or "version" in result.stderr


def test_cli_validate_auto_discovery(cli_runner, config_fs, mocker):
    """Проверяет автообнаружение модели Settings."""
    fs, project_root = config_fs
    fs.create_file("config.yml", contents="app_name: MyApp\nversion: 1.0")

    # Мокаем импорт модели для одного из путей автообнаружения
    mocker.patch("chutils.commands.validate._import_string",
                 side_effect=lambda x: Settings if "context:Settings" in x else None)

    result = cli_runner.invoke(["validate"])

    assert result.exit_code == 0
    assert "Найдена модель:" in result.stdout
    assert "context:Settings" in result.stdout
    assert "успешно прошла валидацию" in result.stdout


def test_cli_validate_model_not_found(cli_runner, config_fs, mocker):
    """Проверяет ошибку, если модель не найдена."""
    fs, project_root = config_fs
    mocker.patch("chutils.commands.validate._import_string", return_value=None)

    result = cli_runner.invoke(["validate"])

    assert result.exit_code == 1
    assert "модель не найдена автоматически" in result.stdout or "модель не найдена автоматически" in result.stderr


def test_cli_validate_import_error(cli_runner, config_fs, mocker):
    """Проверяет ошибку при указании несуществующей модели."""
    fs, project_root = config_fs
    mocker.patch("chutils.commands.validate._import_string", return_value=None)

    result = cli_runner.invoke(["validate", "-m", "non_existent:Model"])

    assert result.exit_code == 1
    assert "Не удалось импортировать модель" in result.stderr or "Не удалось импортировать модель" in result.stdout


def test_cli_validate_no_pydantic(cli_runner, config_fs, mocker):
    """Проверяет поведение при отсутствии Pydantic."""
    fs, project_root = config_fs
    fs.create_file("config.yml", contents="key: val")

    mocker.patch("chutils.commands.validate._import_string", return_value=Settings)

    # Используем unittest.mock.patch.dict напрямую, чтобы избежать проблем с pytest-mock
    with mock.patch.dict("sys.modules", {"pydantic": None}):
        result = cli_runner.invoke(["validate", "-m", "m:M"])
        assert result.exit_code == 1
        assert "Пакет 'pydantic' не установлен" in result.stdout or "Пакет 'pydantic' не установлен" in result.stderr


def test_cli_validate_unexpected_error(cli_runner, config_fs, mocker):
    """Проверяет обработку непредвиденных ошибок."""
    fs, project_root = config_fs
    fs.create_file("config.yml", contents="key: val")
    # Патчим _import_string, чтобы он бросал ошибку
    mocker.patch("chutils.commands.validate._import_string", side_effect=RuntimeError("Boom"))

    result = cli_runner.invoke(["validate", "-m", "m:M"])
    assert result.exit_code == 1
    assert "Boom" in result.stdout or "Boom" in result.stderr
