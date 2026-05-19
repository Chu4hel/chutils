import argparse
import importlib
import json
import os
import sys
from typing import Any

from chutils import config
from chutils.secret_manager import SecretManager


def handle_secrets_set(args: argparse.Namespace):
    """Обработчик команды сохранения секрета."""
    service_name = args.service or config.get_config_value("Secrets", "service_name", "")
    sm = SecretManager(service_name)

    if sm.save_secret(args.key, args.value):
        print(f"[OK] Секрет '{args.key}' успешно сохранен в системном хранилище.")
    else:
        print(f"[ERROR] Не удалось сохранить секрет '{args.key}'. Проверьте доступность keyring.")
        sys.exit(1)


def handle_secrets_delete(args: argparse.Namespace):
    """Обработчик команды удаления секрета."""
    service_name = args.service or config.get_config_value("Secrets", "service_name", "")
    sm = SecretManager(service_name)

    if sm.delete_secret(args.key):
        print(f"[OK] Секрет '{args.key}' успешно удален.")
    else:
        print(f"[ERROR] Не удалось удалить секрет '{args.key}' или он не существовал.")
        sys.exit(1)


def handle_show_paths(args: argparse.Namespace):
    """Обработчик команды вывода путей поиска конфигурации."""
    from chutils.config.manager import _cm

    # Инициализируем пути, если еще нет
    if not config.are_paths_initialized():
        config.get_base_dir()

    base_dir = config.get_base_dir()
    main_path, local_path = config.get_config_paths()

    paths_data = {
        "base_dir": base_dir,
        "main_config": main_path,
        "local_config": local_path,
        "search_markers": _cm.CONFIG_MARKERS
    }

    if args.json:
        print(json.dumps(paths_data, indent=4, ensure_ascii=False))
    else:
        print(f"Корень проекта: {base_dir or 'Не найден'}")
        print(f"Основной конфиг: {main_path or 'Не найден'}")
        print(f"Локальный конфиг: {local_path or 'Не найден'}")
        print("\nСписок маркеров для поиска (в порядке приоритета):")
        for marker in _cm.CONFIG_MARKERS:
            print(f" - {marker}")


def handle_init(args: argparse.Namespace):
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


def _import_string(import_str: str) -> Any:
    """Импортирует объект по строковому пути (например, 'package.module.Class')."""
    try:
        if ':' in import_str:
            module_name, obj_name = import_str.split(':', 1)
        else:
            module_name, obj_name = import_str.rsplit('.', 1)

        module = importlib.import_module(module_name)
        return getattr(module, obj_name)
    except (ImportError, AttributeError, ValueError):
        return None


def handle_validate(args: argparse.Namespace):
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


def main():
    """Точка входа в CLI."""
    parser = argparse.ArgumentParser(
        prog="chutils",
        description="Набор утилит chutils для командной строки."
    )
    subparsers = parser.add_subparsers(dest="command", help="Команды")

    # Секция секретов
    secrets_parser = subparsers.add_parser("secrets", help="Управление секретами")
    secrets_subparsers = secrets_parser.add_subparsers(dest="subcommand", help="Действия с секретами")

    # secrets set <key> <value>
    set_parser = secrets_subparsers.add_parser("set", help="Сохранить секрет")
    set_parser.add_argument("key", help="Имя ключа")
    set_parser.add_argument("value", help="Значение секрета")
    set_parser.add_argument("-s", "--service", help="Имя сервиса (service_name) для keyring")

    # secrets delete <key>
    delete_parser = secrets_subparsers.add_parser("delete", help="Удалить секрет")
    delete_parser.add_argument("key", help="Имя ключа")
    delete_parser.add_argument("-s", "--service", help="Имя сервиса (service_name) для keyring")

    # show-paths
    show_paths_parser = subparsers.add_parser("show-paths", help="Показать пути поиска конфигурации")
    show_paths_parser.add_argument("--json", action="store_true", help="Вывод в формате JSON")

    # init
    init_parser = subparsers.add_parser("init", help="Инициализировать проект")
    init_parser.add_argument("-y", "--yes", action="store_true", help="Автоматически отвечать 'да' на все вопросы")

    # validate
    validate_parser = subparsers.add_parser("validate", help="Валидация конфигурации")
    validate_parser.add_argument("-m", "--model", help="Путь к Pydantic модели (например, 'src.context.Settings')")

    args = parser.parse_args()

    if args.command == "secrets":
        if args.subcommand == "set":
            handle_secrets_set(args)
        elif args.subcommand == "delete":
            handle_secrets_delete(args)
        else:
            secrets_parser.print_help()
    elif args.command == "show-paths":
        handle_show_paths(args)
    elif args.command == "init":
        handle_init(args)
    elif args.command == "validate":
        handle_validate(args)
    else:
        parser.print_help()

    sys.exit(0)


if __name__ == "__main__":
    main()
