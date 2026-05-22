import os
import sys
from pathlib import Path

import pytest

from chutils.cli import main
from chutils.config.generator import PYDANTIC_AVAILABLE


@pytest.fixture
def temp_module(tmp_path):
    """Создает временный модуль с Pydantic моделью для тестов."""
    module_dir = tmp_path / "test_module"
    module_dir.mkdir()
    (module_dir / "__init__.py").touch()

    model_code = """
from pydantic import BaseModel, Field

class SubConfig(BaseModel):
    enabled: bool = Field(default=True, description="Включить подсистему")

class MockConfig(BaseModel):
    app_name: str = Field(default="TestApp", description="Имя приложения")
    sub: SubConfig
"""
    (module_dir / "models.py").write_text(model_code, encoding="utf-8")

    sys.path.insert(0, str(tmp_path))
    yield "test_module.models:MockConfig"
    if str(tmp_path) in sys.path:
        sys.path.remove(str(tmp_path))
    # Удаляем модули из кэша
    if "test_module" in sys.modules: del sys.modules["test_module"]
    if "test_module.models" in sys.modules: del sys.modules["test_module.models"]


@pytest.mark.skipif(not PYDANTIC_AVAILABLE, reason="Pydantic not installed")
def test_cli_template_yaml(mocker, capsys, temp_module):
    """Проверяет генерацию YAML шаблона через CLI."""
    test_args = ["chutils", "template", "--model", temp_module, "--format", "yaml"]
    mocker.patch.object(sys, 'argv', test_args)

    with pytest.raises(SystemExit) as e:
        main()

    captured = capsys.readouterr()
    assert e.value.code == 0
    assert 'app_name: "TestApp"' in captured.out
    assert "# Имя приложения" in captured.out


@pytest.mark.skipif(not PYDANTIC_AVAILABLE, reason="Pydantic not installed")
def test_cli_init_with_model(mocker, capsys, temp_module, tmp_path):
    """Проверяет инициализацию проекта с моделью."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    # Сохраняем текущую директорию
    old_cwd = os.getcwd()
    os.chdir(project_dir)

    try:
        test_args = ["chutils", "init", "-y", "--model", temp_module]
        mocker.patch.object(sys, 'argv', test_args)

        with pytest.raises(SystemExit) as e:
            main()

        captured = capsys.readouterr()
        assert e.value.code == 0

        config_path = Path("config.yml")
        assert config_path.exists()
        content = config_path.read_text(encoding="utf-8")
        assert 'app_name: "TestApp"' in content
        assert "# Имя приложения" in content

    finally:
        os.chdir(old_cwd)
