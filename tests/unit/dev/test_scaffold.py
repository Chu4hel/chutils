from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from chutils.dev.scaffold import Scaffolder, to_camel_case
from chutils.exceptions import CommandError


def test_to_camel_case() -> None:
    assert to_camel_case("user_profile") == "UserProfile"
    assert to_camel_case("order") == "Order"
    assert to_camel_case("my_super_module_name") == "MySuperModuleName"


def test_scaffolder_validation_invalid_names() -> None:
    # Имя не может быть пустым
    scaffolder = Scaffolder(module_name="", output_dir="dummy")
    with pytest.raises(CommandError, match="Имя модуля не может быть пустым"):
        scaffolder.validate()

    # Невалидные символы или начало с цифры
    invalid_names = ["1module", "module-name", "module.name", "Module", "модуль"]
    for name in invalid_names:
        scaffolder = Scaffolder(module_name=name, output_dir="dummy")
        with pytest.raises(CommandError, match="Некорректное имя модуля"):
            scaffolder.validate()

    # Ключевые слова Python
    keywords = ["import", "class", "def", "return", "try", "for"]
    for kw in keywords:
        scaffolder = Scaffolder(module_name=kw, output_dir="dummy")
        with pytest.raises(CommandError, match="является зарезервированным ключевым словом"):
            scaffolder.validate()


def test_scaffolder_output_directory_exists(tmp_path: Path) -> None:
    module_dir = tmp_path / "test_module"
    module_dir.mkdir()

    # Создаем какой-нибудь файл, чтобы директория была не пустой
    dummy_file = module_dir / "dummy.txt"
    dummy_file.write_text("content", encoding="utf-8")

    scaffolder = Scaffolder(module_name="test_module", output_dir=str(module_dir))

    # Без force=True должна выброситься ошибка
    with pytest.raises(CommandError, match="уже существует и не пуста"):
        scaffolder.validate()

    # С force=True валидация должна проходить успешно
    scaffolder_force = Scaffolder(module_name="test_module", output_dir=str(module_dir), force=True)
    scaffolder_force.validate()


def test_scaffolder_scaffold_generation(tmp_path: Path) -> None:
    module_dir = tmp_path / "my_test_module"

    scaffolder = Scaffolder(module_name="my_test_module", output_dir=str(module_dir))
    scaffolder.scaffold()

    # Проверяем, что все директории созданы
    assert module_dir.exists()
    assert (module_dir / "domain").is_dir()
    assert (module_dir / "application").is_dir()
    assert (module_dir / "infrastructure").is_dir()
    assert (module_dir / "presentation").is_dir()

    # Проверяем файлы
    expected_files = [
        "__init__.py",
        "container.py",
        "domain/__init__.py",
        "domain/entities.py",
        "domain/value_objects.py",
        "domain/repositories.py",
        "application/__init__.py",
        "application/use_cases.py",
        "infrastructure/__init__.py",
        "infrastructure/repositories.py",
        "infrastructure/db_adapters.py",
        "presentation/__init__.py",
        "presentation/cli.py",
        "presentation/api.py",
    ]

    for rel_path in expected_files:
        assert (module_dir / rel_path).is_file(), f"Файл {rel_path} не найден."

    # Проверяем плейсхолдеры в файлах
    init_content = (module_dir / "__init__.py").read_text(encoding="utf-8")
    assert "MyTestModule" in init_content
    assert "MyTestModuleConfig" in init_content

    entities_content = (module_dir / "domain/entities.py").read_text(encoding="utf-8")
    assert "class MyTestModule(Entity):" in entities_content


def test_scaffolder_generated_code_quality(tmp_path: Path) -> None:
    """Запуск ruff и mypy на сгенерированном коде для проверки качества и типизации."""
    module_dir = tmp_path / "valid_module"
    scaffolder = Scaffolder(module_name="valid_module", output_dir=str(module_dir))
    scaffolder.scaffold()

    # Проверка синтаксиса Python через компиляцию
    for root, _, files in os.walk(module_dir):
        for file in files:
            if file.endswith(".py"):
                file_path = Path(root) / file
                with open(file_path, "r", encoding="utf-8") as f:
                    try:
                        compile(f.read(), str(file_path), "exec")
                    except SyntaxError as e:
                        pytest.fail(f"Синтаксическая ошибка в сгенерированном файле {file_path}: {e}")

    # Запуск ruff (если доступен в системе)
    if shutil.which("ruff"):
        result = subprocess.run(
            ["ruff", "check", str(module_dir)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Ruff linting failed on generated module:\n{result.stdout}\n{result.stderr}"

    # Запуск mypy (если доступен в системе)
    if shutil.which("mypy"):
        # Создаем временный файл конфигурации mypy или запускаем напрямую
        # Нам нужно убедиться, что mypy проверяет строго
        result = subprocess.run(
            [sys.executable, "-m", "mypy", "--strict", str(module_dir)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Mypy strict validation failed on generated module:\n{result.stdout}\n{result.stderr}"
