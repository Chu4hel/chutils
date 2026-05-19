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
            help="Путь к модели (например, 'myapp.context:Settings'). Если не указан, ищет 'Settings' в context.py/config.py."
        )
        validate_parser.set_defaults(handler=self.handle)

    def handle(self, args: argparse.Namespace):
        """Обработчик команды валидации конфигурации."""
        print("--- Валидация конфигурации ---")

        model_class = None
        if args.model:
            model_class = _import_string(args.model)
            if not model_class:
                print(f"[ERROR] Не удалось импортировать модель '{args.model}'.")
                sys.exit(1)
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
                print("[ERROR] Pydantic модель не найдена. Укажите путь через --model.")
                sys.exit(1)

        try:
            from pydantic import ValidationError
        except ImportError:
            print("[ERROR] Пакет 'pydantic' не установлен. Установите его: pip install pydantic")
            sys.exit(1)

        try:
            # Пытаемся загрузить конфиг через модель
            config.get_config(model=model_class)
            print("[OK] Конфигурация успешно прошла валидацию.")
        except ValidationError as e:
            print("\n[FAIL] Ошибки валидации:")
            for error in e.errors():
                loc = " -> ".join(str(i) for i in error['loc'])
                msg = error['msg']
                print(f"  - {loc}: {msg}")
            sys.exit(1)
        except Exception as e:
            print(f"[ERROR] Произошла ошибка при валидации: {e}")
            sys.exit(1)
