from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from .base import BaseCommand
from .utils import _import_string


class EnvCommand(BaseCommand):
    """
    Управление и валидация переменных окружения.

    Позволяет проверять наличие и корректность типов переменных окружения
    с использованием декларативных манифестов.
    """

    def register(self, subparsers: argparse._SubParsersAction[Any]) -> None:
        """Регистрирует команду env и её подкоманды в argparse.

        Args:
            subparsers: Объект subparsers для добавления подкоманд.
        """
        env_parser = subparsers.add_parser(
            "env",
            help="Управление переменными окружения",
            description="Команды для работы с декларативными манифестами переменных окружения.",
        )
        env_parser.set_defaults(handler=self.handle)

        env_subparsers = env_parser.add_subparsers(
            dest="subcommand", help="Доступные действия"
        )

        # env validate
        validate_parser = env_subparsers.add_parser(
            "validate",
            help="Валидация переменных окружения по манифесту",
            description="Проверяет переменные окружения по декларативному манифесту.",
        )
        validate_parser.add_argument(
            "-m", "--manifest",
            help="Строковый путь к манифесту (например, 'myapp.env:AppEnv'). "
                 "Если не указан, пытается найти в конфигурационных файлах проекта."
        )

    def handle(self, args: argparse.Namespace) -> None:
        """Обработчик команды env.

        Args:
            args: Объект Namespace с аргументами командной строки.
        """
        if args.subcommand == "validate":
            self.handle_validate(args)
        else:
            # Выводим помощь
            parser = argparse.ArgumentParser()
            subparsers = parser.add_subparsers()
            self.register(subparsers)
            parser.parse_args(["env", "--help"])

    def handle_validate(self, args: argparse.Namespace) -> None:
        """Выполняет валидацию переменных окружения по манифесту.

        Args:
            args: Объект Namespace с аргументами.
        """
        from chutils.exceptions import CommandError, OptionalDependencyError, EnvValidationError
        from chutils.env import PYDANTIC_AVAILABLE

        if not PYDANTIC_AVAILABLE:
            raise OptionalDependencyError(
                "Pydantic не установлен.",
                dependency="pydantic",
                hint="Установите его: pip install chutils[pydantic]"
            )

        manifest_path = args.manifest
        if not manifest_path:
            # Пытаемся найти автоматически
            manifest_path = self._find_manifest_path()

        if not manifest_path:
            raise CommandError(
                "Манифест переменных окружения не найден.",
                hint="Укажите путь к манифесту через аргумент -m/--manifest "
                     "или пропишите его в pyproject.toml / chutils.yaml."
            )

        # Гарантируем, что текущая папка в sys.path
        if str(Path.cwd()) not in sys.path:
            sys.path.insert(0, str(Path.cwd()))

        self.console.print(f"[INFO] Загрузка манифеста окружения: '{manifest_path}'...")
        manifest_class = _import_string(manifest_path)
        if not manifest_class:
            raise CommandError(
                f"Не удалось импортировать класс манифеста '{manifest_path}'.",
                hint="Проверьте правильность написания пути в формате 'module.path:ClassName'."
            )

        from chutils.env import BaseEnvManifest
        if not issubclass(manifest_class, BaseEnvManifest):
            raise CommandError(
                f"Класс '{manifest_path}' не является подклассом BaseEnvManifest.",
                hint="Убедитесь, что ваш манифест наследуется от chutils.env.BaseEnvManifest."
            )

        try:
            # Выполняем загрузку и валидацию
            manifest_class.load()
            self.console.print("[bold green][OK] Переменные окружения успешно прошли валидацию.[/bold green]")
        except EnvValidationError as e:
            self.console.print(e)
            sys.exit(1)
        except Exception as e:
            raise CommandError(f"Произошла ошибка при валидации: {e}") from e

    def _find_manifest_path(self) -> str | None:
        """Пытается автоматически обнаружить путь к манифесту в конфиге проекта."""
        # 1. Из основного конфига
        try:
            from chutils import get_config_value
            manifest = get_config_value("env", "manifest", None)
            if manifest:
                return str(manifest)
        except Exception:
            pass

        # 2. Из pyproject.toml
        try:
            from chutils.config.utils import find_project_root

            root = find_project_root()
            pyproject_path = root / "pyproject.toml"
            if pyproject_path.exists():
                data = {}
                try:
                    import tomllib
                    with open(pyproject_path, "rb") as f:
                        data = tomllib.load(f)
                except ImportError:
                    try:
                        import tomli
                        with open(pyproject_path, "rb") as f:
                            data = tomli.load(f)
                    except ImportError:
                        # Текстовый фолбек, если библиотек нет в рантайме
                        with open(pyproject_path, encoding="utf-8") as f:
                            content = f.read()
                        in_section = False
                        for line in content.splitlines():
                            line = line.strip()
                            if not line or line.startswith("#"):
                                continue
                            if line.startswith("[") and line.endswith("]"):
                                in_section = (line == "[tool.chutils.env]")
                                continue
                            if in_section and "=" in line:
                                k, v = line.split("=", 1)
                                if k.strip() == "manifest":
                                    val = v.strip().strip('"').strip("'")
                                    return val

                if isinstance(data, dict):
                    tool_dict = data.get("tool", {})
                    if isinstance(tool_dict, dict):
                        chutils_dict = tool_dict.get("chutils", {})
                        if isinstance(chutils_dict, dict):
                            env_dict = chutils_dict.get("env", {})
                            if isinstance(env_dict, dict):
                                manifest = env_dict.get("manifest")
                                if manifest:
                                    return str(manifest)
        except Exception:
            pass

        return None
