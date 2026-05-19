import argparse
import json
import sys

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
    else:
        parser.print_help()

    sys.exit(0)


if __name__ == "__main__":
    main()
