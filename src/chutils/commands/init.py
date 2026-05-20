import argparse
import os

from .base import BaseCommand


class InitCommand(BaseCommand):
    """
    Инициализация нового проекта с использованием chutils.
    
    Создает базовый файл config.yml с рекомендуемыми настройками и
    обновляет .gitignore для предотвращения утечки секретов и логов.
    """

    def register(self, subparsers: argparse._SubParsersAction):
        init_parser = subparsers.add_parser(
            "init",
            help="Инициализировать новый проект",
            description="Быстрое создание структуры конфигурации и настройка исключений git."
        )
        init_parser.add_argument(
            "-y", "--yes",
            action="store_true",
            help="Автоматически отвечать 'да' на все вопросы (использовать настройки по умолчанию)"
        )
        init_parser.add_argument(
            "-m", "--model",
            help="Путь к Pydantic модели для генерации детального конфига (например, 'myapp.config:Settings')"
        )
        init_parser.set_defaults(handler=self.handle)

    def handle(self, args: argparse.Namespace):
        """Обработчик команды инициализации проекта."""
        print("--- Инициализация проекта chutils ---")

        if args.yes:
            project_name = "Project"
        else:
            try:
                project_name = input(f"Введите имя проекта [Project]: ").strip() or "Project"
            except EOFError:
                project_name = "Project"

        # Создаем config.yml
        config_path = "config.yml"
        if os.path.exists(config_path):
            if not args.yes:
                try:
                    confirm = input(f"Файл {config_path} уже существует. Перезаписать? [y/N]: ").lower()
                except EOFError:
                    confirm = 'n'
                if confirm != 'y':
                    print("[SKIP] Создание config.yml отменено.")
                    config_path = None
            else:
                print(f"[INFO] Перезапись {config_path}...")

        if config_path:
            if args.model:
                # Пытаемся сгенерировать на основе модели
                from ..config.generator import generate_yaml_template, PYDANTIC_AVAILABLE
                import importlib
                import sys
                from pathlib import Path

                if not PYDANTIC_AVAILABLE:
                    print("[WARN] Pydantic не установлен. Будет создан базовый конфиг.")
                    config_content = self._get_default_config(project_name)
                else:
                    try:
                        if ":" in args.model:
                            module_path, class_name = args.model.split(":")
                        else:
                            parts = args.model.rsplit(".", 1)
                            if len(parts) == 2:
                                module_path, class_name = parts
                            else:
                                raise ValueError("Формат модели должен быть 'module:Class' или 'module.Class'")

                        sys.path.insert(0, str(Path.cwd()))
                        module = importlib.import_module(module_path)
                        model_class = getattr(module, class_name)

                        config_content = f"# Конфигурация проекта {project_name}\n\n"
                        config_content += generate_yaml_template(model_class)
                    except Exception as e:
                        print(f"[WARN] Ошибка при загрузке модели '{args.model}': {e}")
                        print("[INFO] Будет создан базовый конфиг.")
                        config_content = self._get_default_config(project_name)
            else:
                config_content = self._get_default_config(project_name)

            with open(config_path, "w", encoding="utf-8") as f:
                f.write(config_content)
            print(f"[OK] Файл {config_path} создан.")

        # Обновляем .gitignore
        gitignore_path = ".gitignore"
        gitignore_entries = [
            "config.local.yml", "config.local.yaml", "config.local.ini", "config.local.json",
            "*.log", "logs/"
        ]

        existing_content = ""
        if os.path.exists(gitignore_path):
            with open(gitignore_path, "r", encoding="utf-8") as f:
                existing_content = f.read()

        existing_lines = existing_content.splitlines()
        new_entries = [e for e in gitignore_entries if e not in existing_lines]

        if new_entries:
            with open(gitignore_path, "a", encoding="utf-8") as f:
                if existing_content and not existing_content.endswith("\n"):
                    f.write("\n")
                f.write("\n# chutils\n")
                for entry in new_entries:
                    f.write(f"{entry}\n")
            print(f"[OK] Файл {gitignore_path} обновлен.")
        else:
            print(f"[SKIP] Файл {gitignore_path} уже содержит необходимые исключения.")

    def _get_default_config(self, project_name: str) -> str:
        return f"""# Конфигурация проекта {project_name}

Logging:
  level: INFO
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  file_path: "app.log"
  max_bytes: 10485760  # 10MB
  backup_count: 5

Secrets:
  service_name: "{project_name.lower().replace(' ', '_')}"
"""
