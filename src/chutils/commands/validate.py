import argparse
import sys

from chutils import config
from .base import BaseCommand
from .utils import _import_string


class ValidateCommand(BaseCommand):
    """
    Валидация конфигурации проекта.
    
    Проверяет, что текущие файлы конфигурации (YAML, JSON или INI) 
    соответствуют структуре и типам данных заданной Pydantic-модели.
    """

    def register(self, subparsers: argparse._SubParsersAction):
        validate_parser = subparsers.add_parser(
            "validate",
            help="Проверить корректность конфигурации",
            description="Валидация настроек с использованием Pydantic моделей."
        )
        validate_parser.add_argument(
            "-m", "--model",
            help="Путь к модели (например, 'myapp.context:Settings'). "
                 "Если не указан, ищет 'Settings' в context.py/config.py."
        )
        validate_parser.set_defaults(handler=self.handle)

    def handle(self, args: argparse.Namespace):
        """Обработчик команды валидации конфигурации."""
        from ..exceptions import CommandError, OptionalDependencyError
        print("--- Валидация конфигурации ---")

        model_class = None
        if args.model:
            model_class = _import_string(args.model)
            if not model_class:
                raise CommandError(
                    f"Не удалось импортировать модель '{args.model}'.",
                    hint="Убедитесь, что модуль существует и путь к классу указан верно в формате 'module:Class'."
                )
        else:
            # Авто-обнаружение модели
            search_paths = [
                "src.context:Settings", "src.config:Settings",
                "context:Settings", "config:Settings"
            ]
            print("[INFO] Поиск Pydantic модели (Settings)...")
            for path in search_paths:
                model_class = _import_string(path)
                if model_class:
                    print(f"[OK] Найдена модель: {path}")
                    break

            if not model_class:
                raise CommandError(
                    "Pydantic модель не найдена автоматически.",
                    hint="Укажите путь к вашей Pydantic модели через аргумент --model. "
                         "Пример: chutils validate --model myapp.config:Settings"
                )

        try:
            from pydantic import ValidationError
        except ImportError:
            raise OptionalDependencyError(
                "Пакет 'pydantic' не установлен.",
                dependency="pydantic",
                hint="Установите его для поддержки валидации: pip install chutils[pydantic]"
            )

        try:
            # Пытаемся загрузить конфиг через модель
            config.get_config(model=model_class)
            self.console.print("[bold green][OK] Конфигурация успешно прошла валидацию.[/bold green]")
        except ValidationError as e:
            self.console.print("\n[bold red]ОШИБКИ ВАЛИДАЦИИ:[/bold red]")
            for error in e.errors():
                loc = " -> ".join(str(i) for i in error['loc'])
                msg = error['msg']
                print(f"  - {loc}: {msg}")
            sys.exit(1)
        except Exception as e:
            raise CommandError(f"Произошла ошибка при валидации: {e}") from e
