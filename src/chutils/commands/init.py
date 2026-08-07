from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

from .base import BaseCommand


class InitCommand(BaseCommand):
    """
    Инициализация нового проекта с использованием chutils.
    
    Создает базовый или расширенный файл config.yml с рекомендуемыми настройками,
    настраивает Git-исключения, а также опционально разворачивает окружение,
    миграции, CI/CD, диагностику и скелет чистой архитектуры.
    """

    def register(self, subparsers: argparse._SubParsersAction[Any]) -> None:
        """Регистрирует команду init в argparse.

        Args:
            subparsers: Объект subparsers для добавления подкоманд.
        """
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
        init_parser.add_argument(
            "-t", "--template",
            choices=["default", "vk-miniapp", "vk-bot", "vk-bot-miniapp"],
            default="default",
            help="Выбор готового шаблона проекта (default, vk-miniapp, vk-bot, vk-bot-miniapp)"
        )
        init_parser.set_defaults(handler=self.handle)

    def _ask_yes_no(self, prompt: str, default: bool) -> bool:
        """Спрашивает у пользователя булево значение."""
        default_str = "Y/n" if default else "y/N"
        try:
            val = input(f"{prompt} [{default_str}]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return default
        if not val:
            return default
        return val in ("y", "yes", "true", "1")

    def _ask_str(self, prompt: str, default: str) -> str:
        """Спрашивает у пользователя строку."""
        try:
            val = input(f"{prompt} [{default}]: ").strip()
        except (EOFError, KeyboardInterrupt):
            return default
        return val if val else default

    def handle(self, args: argparse.Namespace) -> None:
        """Обработчик команды инициализации проекта.

        Args:
            args: Объект Namespace с аргументами командной строки.
        """
        print("--- Инициализация проекта chutils ---")

        if args.yes:
            project_name = "Project"
        else:
            try:
                project_name = input("Введите имя проекта [Project]: ").strip() or "Project"
            except EOFError:
                project_name = "Project"

        # Создаем config.yml
        config_path: str | None = "config.yml"
        if config_path and os.path.exists(config_path):
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

        # Обработка выбора шаблона проекта
        if hasattr(args, "template") and args.template != "default":
            from chutils.scaffold import unpack_template
            print(f"[INFO] Создание проекта по шаблону '{args.template}'...")
            unpack_template(args.template, os.getcwd(), context={"project_name": project_name})
            print(f"[OK] Проект по шаблону '{args.template}' успешно инициализирован!")
            return
        setup_db = False
        setup_alembic = False
        setup_audit = False
        setup_cloud_secrets = False
        setup_env = False
        setup_ai_ready = False
        setup_metrics = False
        setup_ci = False
        setup_pypi = False
        setup_diagnostics = False
        setup_scaffold = False

        if config_path and not args.yes:
            setup_db = self._ask_yes_no("Настроить конфигурацию Базы Данных (Database)?", False)
            if setup_db:
                setup_alembic = self._ask_yes_no("Инициализировать директорию миграций Alembic (migrations/)?", False)
            setup_audit = self._ask_yes_no("Настроить криптографический аудит-лог (chutils.audit)?", False)
            setup_cloud_secrets = self._ask_yes_no("Настроить интеграцию с облачными провайдерами секретов (AWS/GCP)?", False)
            setup_env = self._ask_yes_no("Создать декларативные файлы окружения .env и .env.example?", False)
            setup_ai_ready = self._ask_yes_no("Сгенерировать AI-Ready конфигурацию (ai-lint.toml, GEMINI.md)?", False)
            setup_metrics = self._ask_yes_no("Добавить шаблон настройки экспорта метрик Prometheus?", False)
            setup_ci = self._ask_yes_no("Сгенерировать GitHub Actions CI workflow?", False)
            setup_pypi = self._ask_yes_no("Проверить скорость PyPI-зеркал и настроить оптимальное зеркало?", False)
            setup_diagnostics = self._ask_yes_no("Настроить модуль диагностики здоровья (FastAPI/Flask health эндпоинт)?", False)
            setup_scaffold = self._ask_yes_no("Развернуть скелет Clean Architecture (через chutils dev scaffold)?", False)

        if config_path:
            if args.model:
                # Пытаемся сгенерировать на основе модели
                from ..config.generator import generate_yaml_template, PYDANTIC_AVAILABLE
                import importlib
                if not PYDANTIC_AVAILABLE:
                    print("[WARN] Pydantic не установлен. Будет создан базовый конфиг.")
                    config_content = self._get_default_config(
                        project_name, setup_db, setup_audit, setup_cloud_secrets, setup_metrics, setup_diagnostics
                    )
                else:
                    try:
                        if ":" in args.model:
                            module_path, class_name = args.model.split(":")
                        else:
                            parts = args.model.rsplit(".", 1)
                            if len(parts) == 2:
                                module_path, class_name = parts
                            else:
                                from ..exceptions import CommandError
                                raise CommandError(
                                    f"Некорректный формат модели: '{args.model}'",
                                    hint="Используйте формат 'module:Class' или 'module.Class'. "
                                         "Пример: 'myapp.config:Settings'"
                                )

                        sys.path.insert(0, str(Path.cwd()))
                        module = importlib.import_module(module_path)
                        model_class = getattr(module, class_name)

                        config_content = f"# Конфигурация проекта {project_name}\n\n"
                        config_content += generate_yaml_template(model_class)
                    except Exception as e:
                        print(f"[WARN] Ошибка при загрузке модели '{args.model}': {e}")
                        print("[INFO] Будет создан базовый конфиг.")
                        config_content = self._get_default_config(
                            project_name, setup_db, setup_audit, setup_cloud_secrets, setup_metrics, setup_diagnostics
                        )
            else:
                config_content = self._get_default_config(
                    project_name, setup_db, setup_audit, setup_cloud_secrets, setup_metrics, setup_diagnostics
                )

            with open(config_path, "w", encoding="utf-8") as f:
                f.write(config_content)
            print(f"[OK] Файл {config_path} создан.")

        # 1. Alembic migrations
        if setup_alembic:
            try:
                from .db import _init_migrations_dir
                _init_migrations_dir(Path("migrations"))
            except Exception as e:
                print(f"[WARN] Не удалось инициализировать директорию миграций Alembic: {e}")

        # 2. Декларативное окружение (.env / .env.example)
        if setup_env:
            try:
                env_file = Path(".env")
                env_example = Path(".env.example")
                if not env_example.exists():
                    with open(env_example, "w", encoding="utf-8") as f:
                        f.write("# Декларативное окружение проекта\nDATABASE_URL=sqlite+aiosqlite:///./database.db\nPORT=8000\n")
                if not env_file.exists():
                    with open(env_file, "w", encoding="utf-8") as f:
                        f.write("# Локальное окружение\nDATABASE_URL=sqlite+aiosqlite:///./database.db\nPORT=8000\n")
                print("[OK] Файлы .env и .env.example созданы.")
            except Exception as e:
                print(f"[WARN] Не удалось создать файлы окружения: {e}")

        # 3. AI-Ready конфигурация
        if setup_ai_ready:
            try:
                ai_lint_file = Path("ai-lint.toml")
                if not ai_lint_file.exists():
                    with open(ai_lint_file, "w", encoding="utf-8") as f:
                        f.write("[ai-lint]\nstrict = false\nignore = [\".git\", \".venv\", \"__pycache__\", \"build\", \"dist\", \"docs\", \"tests\", \"examples\"]\nrules = []\n")
                
                gemini_file = Path("GEMINI.md")
                if not gemini_file.exists():
                    with open(gemini_file, "w", encoding="utf-8") as f:
                        f.write("# Контекст проекта ИИ\n\nЭтот файл содержит информацию о структуре проекта для ассистентов ИИ.\n")
                print("[OK] Файлы ai-lint.toml и GEMINI.md созданы.")
            except Exception as e:
                print(f"[WARN] Не удалось настроить AI-Ready файлы: {e}")

        # 4. GitHub Actions CI/CD
        if setup_ci:
            try:
                from ..dev.github_actions import generate_workflow_yaml
                ci_path = Path(".github/workflows/ci.yml")
                from chutils.fs import ensure_dir
                ensure_dir(ci_path.parent)
                yaml_content = generate_workflow_yaml(
                    python_versions=["3.10", "3.11", "3.12", "3.13"],
                    with_pytest=True,
                    with_mypy=True,
                    with_ruff=True,
                    with_ai_lint=True,
                )
                with open(ci_path, "w", encoding="utf-8") as f:
                    f.write(yaml_content)
                print(f"[OK] Файл {ci_path} создан.")
            except Exception as e:
                print(f"[WARN] Не удалось настроить GitHub Actions CI: {e}")

        # 5. Тестирование зеркал PyPI
        if setup_pypi:
            try:
                from .pypi import DEFAULT_MIRRORS, measure_mirror, find_best_mirror
                print("[INFO] Тестирование доступности PyPI-зеркал...")
                results = []
                for mirror in DEFAULT_MIRRORS[:3]:  # Проверим первые 3 зеркала для скорости
                    res = measure_mirror(mirror, "chutils")
                    results.append(res)
                best_mirror = find_best_mirror(results, "https://pypi.org/simple/")
                if best_mirror:
                    print(f"[OK] Рекомендуемое зеркало: {best_mirror}")
                    # Опционально пропишем в pyproject.toml
                    pyproject_path = Path("pyproject.toml")
                    if pyproject_path.exists():
                        with open(pyproject_path, "r", encoding="utf-8") as f:
                            pyproject_content = f.read()
                        if "[[tool.uv.index]]" not in pyproject_content and best_mirror != "https://pypi.org/simple/":
                            with open(pyproject_path, "a", encoding="utf-8") as f:
                                f.write(f"\n[[tool.uv.index]]\nname = \"custom-mirror\"\nurl = \"{best_mirror}\"\ndefault = true\n")
                            print("[OK] Зеркало сохранено в pyproject.toml.")
            except Exception as e:
                print(f"[WARN] Не удалось настроить зеркало PyPI: {e}")

        # 6. Модуль диагностики здоровья (health эндпоинт)
        if setup_diagnostics:
            try:
                health_file = Path("health.py")
                if not health_file.exists():
                    with open(health_file, "w", encoding="utf-8") as f:
                        f.write('''"""Эндпоинт диагностики здоровья системы (health check)."""

from fastapi import FastAPI
from chutils.diagnostics import get_fastapi_health_handler
from chutils.diagnostics.manager import default_manager

app = FastAPI()
app.add_api_route("/health", get_fastapi_health_handler(default_manager), methods=["GET"])
''')
                    print("[OK] Файл health.py создан.")
            except Exception as e:
                print(f"[WARN] Не удалось создать эндпоинт диагностики: {e}")

        # 7. Декларативный CLI Clean Architecture (dev scaffold)
        if setup_scaffold:
            try:
                scaffold_module_name = self._ask_str("Введите имя первого Clean Arch модуля", "app_module")
                from ..dev.scaffold import Scaffolder
                scaffolder = Scaffolder(module_name=scaffold_module_name, output_dir=f"./src/{scaffold_module_name}")
                scaffolder.scaffold()
                print(f"[OK] Скелет модуля Clean Arch {scaffold_module_name} создан.")
            except Exception as e:
                print(f"[WARN] Не удалось сгенерировать Clean Arch структуру: {e}")

        # Обновляем .gitignore
        gitignore_path = ".gitignore"
        gitignore_entries = [
            "config.local.yml", "config.local.yaml", "config.local.ini", "config.local.json",
            "*.log", "logs/"
        ]

        existing_content = ""
        if os.path.exists(gitignore_path):
            with open(gitignore_path, encoding="utf-8") as f:
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

    def _get_default_config(
        self,
        project_name: str,
        setup_db: bool = False,
        setup_audit: bool = False,
        setup_cloud_secrets: bool = False,
        setup_metrics: bool = False,
        setup_diagnostics: bool = False,
    ) -> str:
        project_name_lower = project_name.lower().replace(' ', '_')
        content = f"""# Конфигурация проекта {project_name}

Logging:
  log_level: INFO
  log_file_name: "app.log"
  max_bytes: 10485760  # 10MB
  backup_count: 5

Secrets:
  service_name: "{project_name_lower}"
"""
        if setup_cloud_secrets:
            content += """  # Cloud Secrets Integration:
  # provider: aws  # aws / gcp
  # region_name: us-east-1
  # project_id: ""
"""

        if setup_db:
            content += """
Database:
  url: "sqlite+aiosqlite:///./database.db"
  echo: false
  pool_size: 5
  max_overflow: 10
  migrations_path: "migrations"
"""

        if setup_audit:
            content += """
Audit:
  backend: "file"  # file / sqlite / postgres
  log_path: "logs/audit.log"
  rotate_backup_count: 10
  rotate_max_bytes: 10485760
  enable_hash_chaining: true
"""

        if setup_metrics:
            content += """
Metrics:
  prometheus_port: 8000
  prometheus_collect_interval: 15
"""

        if setup_diagnostics:
            content += """
Diagnostics:
  check_interval: 60
  critical_only: false
"""
        return content

