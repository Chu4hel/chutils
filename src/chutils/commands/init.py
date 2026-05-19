import argparse
import os

from .base import BaseCommand


class InitCommand(BaseCommand):
    """Инициализация проекта и создание шаблона конфигурации."""

    def register(self, subparsers: argparse._SubParsersAction):
        init_parser = subparsers.add_parser("init", help="Инициализировать проект")
        init_parser.add_argument("-y", "--yes", action="store_true", help="Автоматически отвечать 'да' на все вопросы")
        init_parser.set_defaults(handler=self.handle)

    def handle(self, args: argparse.Namespace):
        """Обработчик команды инициализации проекта."""
        print("--- Инициализация проекта chutils ---")

        if args.yes:
            project_name = "Project"
        else:
            try:
                project_name = input("Введите имя проекта [Project]: ").strip() or "Project"
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
            # file_path указываем просто именем, так как библиотека сама подставит logs/
            config_content = f"""# Конфигурация проекта {project_name}

Logging:
  level: INFO
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  file_path: "app.log"
  max_bytes: 10485760  # 10MB
  backup_count: 5

Secrets:
  service_name: "{project_name.lower().replace(' ', '_')}"
"""
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
