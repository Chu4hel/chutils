from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path
from typing import Any

from .base import BaseCommand
from ..config.generator import (
    generate_yaml_template,
    generate_env_template,
    generate_json_schema,
    PYDANTIC_AVAILABLE
)


class TemplateCommand(BaseCommand):
    """
    Генерация шаблонов конфигурации на основе Pydantic моделей.
    """

    def register(self, subparsers: argparse._SubParsersAction[Any]) -> None:
        """Регистрирует команду template в argparse.

        Args:
            subparsers: Объект subparsers для добавления подкоманд.
        """
        template_parser = subparsers.add_parser(
            "template",
            help="Сгенерировать шаблон конфигурации",
            description="Создает файл config.yml, .env или JSON-схему на основе вашей Pydantic модели."
        )
        template_parser.add_argument(
            "-m", "--model",
            required=True,
            help="Путь к Pydantic модели (например, 'myapp.config:Settings')"
        )
        template_parser.add_argument(
            "-f", "--format",
            choices=["yaml", "env", "json-schema"],
            default="yaml",
            help="Формат вывода (по умолчанию: yaml)"
        )
        template_parser.add_argument(
            "-o", "--output",
            help="Путь к файлу для сохранения (по умолчанию: вывод в консоль)"
        )
        template_parser.set_defaults(handler=self.handle)

    def handle(self, args: argparse.Namespace) -> None:
        """Обработчик команды генерации шаблона.

        Args:
            args: Объект Namespace с аргументами командной строки.
        """
        from ..exceptions import CommandError, OptionalDependencyError
        if not PYDANTIC_AVAILABLE:
            raise OptionalDependencyError(
                "Pydantic не установлен.",
                dependency="pydantic",
                hint="Установите его: pip install chutils[pydantic] или poetry add pydantic"
            )

        # 1. Динамический импорт модели
        try:
            if ":" in args.model:
                module_path, class_name = args.model.split(":")
            else:
                # Пытаемся разделить по последней точке
                parts = args.model.rsplit(".", 1)
                if len(parts) == 2:
                    module_path, class_name = parts
                else:
                    raise CommandError(
                        f"Некорректный формат пути к модели: '{args.model}'",
                        hint="Используйте 'module:Class' или 'module.Class'. Пример: 'myapp.config:Settings'"
                    )

            # Добавляем текущую директорию в path, чтобы можно было импортировать локальные модули
            sys.path.insert(0, str(Path.cwd()))
            module = importlib.import_module(module_path)
            model_class = getattr(module, class_name)
        except (ImportError, AttributeError, CommandError) as e:
            if isinstance(e, CommandError):
                raise e
            raise CommandError(
                f"Не удалось импортировать модель '{args.model}': {e}",
                hint="Убедитесь, что модуль существует и путь к классу указан верно."
            ) from e
        except Exception as e:
            raise CommandError(f"Непредвиденная ошибка при импорте модели: {e}") from e

        # 2. Генерация
        result = ""
        try:
            if args.format == "yaml":
                result = generate_yaml_template(model_class)
            elif args.format == "env":
                result = generate_env_template(model_class)
            elif args.format == "json-schema":
                result = generate_json_schema(model_class)
        except Exception as e:
            raise CommandError(f"Ошибка при генерации шаблона: {e}") from e

        # 3. Вывод
        if args.output:
            try:
                with open(args.output, "w", encoding="utf-8") as f:
                    f.write(result)
                self.console.print(f"[green][OK] Шаблон сохранен в {args.output}[/green]")
            except Exception as e:
                raise CommandError(
                    f"Не удалось сохранить файл '{args.output}': {e}",
                    hint="Проверьте права доступа к директории и корректность пути."
                ) from e
        else:
            print(result)
