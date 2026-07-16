from __future__ import annotations

import os
from typing import Any

import pytest

from chutils.exceptions import ChutilsException, EnvValidationError


def test_env_validation_error_inheritance() -> None:
    """Проверяет наследование EnvValidationError от ChutilsException."""
    err = EnvValidationError("Test error")
    assert isinstance(err, ChutilsException)
    assert isinstance(err, Exception)


def test_env_validation_error_str_and_rich() -> None:
    """Проверяет plain-text и rich форматирование EnvValidationError."""
    from rich.table import Table

    errors: list[dict[str, Any]] = [
        {"loc": ("DATABASE_URL",), "msg": "Field required", "type": "missing", "input": None},
        {"loc": ("API_KEY",), "msg": "Input should be a valid string", "type": "string_type", "input": 123}
    ]

    err = EnvValidationError("Validation failed", errors=errors)
    err_str = str(err)

    assert "Validation failed" in err_str
    assert "DATABASE_URL" in err_str
    assert "API_KEY" in err_str

    # Проверка rich-таблицы
    table = err.__rich__()
    assert isinstance(table, Table)
    assert table.title == "Validation failed"
    assert [col.header for col in table.columns] == ["Переменная окружения", "Причина ошибки", "Полученное значение"]


def test_base_env_manifest_success(mocker: Any) -> None:
    """Проверяет успешную загрузку и валидацию манифеста из окружения."""
    from pydantic import Field
    from chutils.env import BaseEnvManifest

    class ConfigEnv(BaseEnvManifest):
        APP_NAME: str
        PORT: int = Field(default=8080)
        DEBUG: bool = Field(default=False)

    mocker.patch.dict(os.environ, {"APP_NAME": "MyApp", "PORT": "3000", "DEBUG": "True"})

    cfg = ConfigEnv.load()
    assert cfg.APP_NAME == "MyApp"
    assert cfg.PORT == 3000
    assert cfg.DEBUG is True


def test_base_env_manifest_validation_failure(mocker: Any) -> None:
    """Проверяет выброс EnvValidationError при невалидных данных окружения."""
    from pydantic import Field
    from chutils.env import BaseEnvManifest

    class ConfigEnv(BaseEnvManifest):
        DATABASE_URL: str
        PORT: int = Field(default=8080)

    # DATABASE_URL отсутствует, PORT имеет некорректный тип
    mocker.patch.dict(os.environ, {"PORT": "not_an_int"})

    with pytest.raises(EnvValidationError) as exc:
        ConfigEnv.load()

    assert "DATABASE_URL" in str(exc.value)
    assert "PORT" in str(exc.value)
    assert len(exc.value.errors) == 2


def test_base_env_manifest_secret_masking(mocker: Any) -> None:
    """Проверяет маскирование секретных полей в сообщениях об ошибках."""
    from pydantic import Field
    from chutils.env import BaseEnvManifest

    class SecureEnv(BaseEnvManifest):
        API_KEY: int = Field(json_schema_extra={"secret": True})

    # Передаем неверный тип, значение должно быть замаскировано
    mocker.patch.dict(os.environ, {"API_KEY": "super_secret_value"})

    with pytest.raises(EnvValidationError) as exc:
        SecureEnv.load()

    # В выводе ошибок значение super_secret_value не должно присутствовать
    err_str = str(exc.value)
    assert "super_secret_value" not in err_str
    assert "***" in err_str


def test_base_env_manifest_without_pydantic(mocker: Any) -> None:
    """Проверяет выброс OptionalDependencyError при отсутствии Pydantic."""
    import sys
    import importlib.util

    # Делаем бэкап модулей chutils
    chutils_backup = {k: v for k, v in sys.modules.items() if k.startswith('chutils')}
    for m in chutils_backup:
        del sys.modules[m]

    try:
        # Патчим find_spec, чтобы pydantic считался неустановленным
        orig_find_spec = importlib.util.find_spec

        def mock_find_spec(name: str, package: str | None = None) -> Any:
            if name == "pydantic":
                return None
            return orig_find_spec(name, package)

        mocker.patch("importlib.util.find_spec", side_effect=mock_find_spec)

        from chutils.env import BaseEnvManifest
        from chutils.exceptions import OptionalDependencyError

        class DummyEnv(BaseEnvManifest):
            pass

        with pytest.raises(OptionalDependencyError) as exc:
            DummyEnv.load()
        assert "pydantic" in str(exc.value.context.get("dependency"))
    finally:
        # Восстанавливаем исходные модули из бэкапа
        to_delete_post = [m for m in sys.modules if m.startswith('chutils')]
        for m in to_delete_post:
            del sys.modules[m]
        for k, v in chutils_backup.items():
            sys.modules[k] = v


def test_chutils_root_exports_without_pydantic(mocker: Any) -> None:
    """Проверяет возможность импортировать BaseEnvManifest из корня даже при отсутствии Pydantic."""
    import sys
    import importlib.util

    chutils_backup = {k: v for k, v in sys.modules.items() if k.startswith('chutils')}
    for m in chutils_backup:
        del sys.modules[m]

    try:
        orig_find_spec = importlib.util.find_spec

        def mock_find_spec(name: str, package: str | None = None) -> Any:
            if name == "pydantic":
                return None
            return orig_find_spec(name, package)

        mocker.patch("importlib.util.find_spec", side_effect=mock_find_spec)

        import chutils
        assert chutils.BaseEnvManifest is not None
        assert chutils.EnvValidationError is not None

        with pytest.raises(Exception) as exc:
            chutils.BaseEnvManifest.load()
        assert "Pydantic не установлен" in str(exc.value)

    finally:
        to_delete_post = [m for m in sys.modules if m.startswith('chutils')]
        for m in to_delete_post:
            del sys.modules[m]
        for k, v in chutils_backup.items():
            sys.modules[k] = v


def test_cli_env_validate_success(mocker: Any) -> None:
    """Проверяет успешное выполнение chutils env validate."""
    import argparse
    from chutils.commands.env import EnvCommand
    from chutils.env import BaseEnvManifest

    class DummyManifest(BaseEnvManifest):
        pass

    mocker.patch.dict(os.environ, {"TEST_VAR": "val"})
    mock_load = mocker.patch.object(DummyManifest, "load")
    mocker.patch("chutils.commands.env._import_string", return_value=DummyManifest)

    cmd = EnvCommand()
    args = argparse.Namespace(subcommand="validate", manifest="myapp.env:AppEnv")
    cmd.handle(args)

    mock_load.assert_called_once()


def test_cli_env_validate_failure(mocker: Any) -> None:
    """Проверяет завершение с кодом 1 при ошибке валидации."""
    import argparse
    from chutils.commands.env import EnvCommand
    from chutils.exceptions import EnvValidationError
    from chutils.env import BaseEnvManifest

    class DummyManifest(BaseEnvManifest):
        pass

    mock_load = mocker.patch.object(DummyManifest, "load", side_effect=EnvValidationError("Validation failed"))
    mocker.patch("chutils.commands.env._import_string", return_value=DummyManifest)

    cmd = EnvCommand()
    args = argparse.Namespace(subcommand="validate", manifest="myapp.env:AppEnv")

    with pytest.raises(SystemExit) as exc:
        cmd.handle(args)

    assert exc.value.code == 1


def test_cli_env_validate_find_manifest_pyproject(mocker: Any, tmp_path: Any) -> None:
    """Проверяет автоопределение пути к манифесту из pyproject.toml."""
    from chutils.commands.env import EnvCommand

    # Создаем временный pyproject.toml
    pyproject_content = b"""
[tool.chutils.env]
manifest = "configured.env:EnvClass"
"""
    mocker.patch("chutils.config.utils.find_project_root", return_value=tmp_path)
    pyproject_file = tmp_path / "pyproject.toml"
    pyproject_file.write_bytes(pyproject_content)

    cmd = EnvCommand()
    path = cmd._find_manifest_path()
    assert path == "configured.env:EnvClass"


def test_cli_env_validate_find_manifest_config(mocker: Any) -> None:
    """Проверяет автоопределение пути к манифесту из конфига chutils."""
    from chutils.commands.env import EnvCommand

    mocker.patch("chutils.get_config_value", return_value="config.env:ConfigEnv")

    cmd = EnvCommand()
    path = cmd._find_manifest_path()
    assert path == "config.env:ConfigEnv"


def test_cli_env_validate_invalid_subclass(mocker: Any) -> None:
    """Проверяет выброс CommandError, если класс не является подклассом BaseEnvManifest."""
    import argparse
    from chutils.commands.env import EnvCommand
    from chutils.exceptions import CommandError

    class InvalidClass:
        pass

    mocker.patch("chutils.commands.env._import_string", return_value=InvalidClass)

    cmd = EnvCommand()
    args = argparse.Namespace(subcommand="validate", manifest="myapp.env:InvalidClass")

    with pytest.raises(CommandError) as exc:
        cmd.handle(args)

    assert "не является подклассом BaseEnvManifest" in str(exc.value)
