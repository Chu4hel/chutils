import argparse
import importlib
import sys
from pathlib import Path

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

    def register(self, subparsers: argparse._SubParsersAction):
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

    def handle(self, args: argparse.Namespace):
        """Обработчик команды генерации шаблона."""
        if not PYDANTIC_AVAILABLE:
            print("[ERROR] Pydantic не установлен. Установите его: pip install chutils[pydantic]")
            sys.exit(1)

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
                    raise ValueError("Некорректный формат пути к модели. Используйте 'module:Class' или 'module.Class'")

            # Добавляем текущую директорию в path, чтобы можно было импортировать локальные модули
            sys.path.insert(0, str(Path.cwd()))
            module = importlib.import_module(module_path)
            model_class = getattr(module, class_name)
        except Exception as e:
            print(f"[ERROR] Не удалось импортировать модель '{args.model}': {e}")
            sys.exit(1)

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
            print(f"[ERROR] Ошибка при генерации шаблона: {e}")
            sys.exit(1)

        # 3. Вывод
        if args.output:
            try:
                with open(args.output, "w", encoding="utf-8") as f:
                    f.write(result)
                print(f"[OK] Шаблон сохранен в {args.output}")
            except Exception as e:
                print(f"[ERROR] Не удалось сохранить файл: {e}")
                sys.exit(1)
        else:
            print(result)
