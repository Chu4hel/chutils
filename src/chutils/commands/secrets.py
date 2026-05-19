import argparse
import sys

from chutils import config
from chutils.secret_manager import SecretManager

from .base import BaseCommand


class SecretsCommand(BaseCommand):
    """Управление секретами в системном хранилище."""

    def register(self, subparsers: argparse._SubParsersAction):
        secrets_parser = subparsers.add_parser("secrets", help="Управление секретами")
        secrets_parser.set_defaults(handler=self.handle)
        secrets_subparsers = secrets_parser.add_subparsers(dest="subcommand", help="Действия с секретами")

        # secrets set <key> <value>
        set_parser = secrets_subparsers.add_parser("set", help="Сохранить секрет")
        set_parser.add_argument("key", help="Имя ключа")
        set_parser.add_argument("value", help="Значение секрета")
        set_parser.add_argument("-s", "--service", help="Имя сервиса (service_name) для keyring")
        set_parser.set_defaults(handler=self.handle_set)

        # secrets delete <key>
        delete_parser = secrets_subparsers.add_parser("delete", help="Удалить секрет")
        delete_parser.add_argument("key", help="Имя ключа")
        delete_parser.add_argument("-s", "--service", help="Имя сервиса (service_name) для keyring")
        delete_parser.set_defaults(handler=self.handle_delete)

    def handle(self, args: argparse.Namespace):
        """Вызывается, если подкоманда не указана."""
        print("Используйте 'chutils secrets --help' для просмотра доступных подкоманд.")

    def handle_set(self, args: argparse.Namespace):
        """Обработчик команды сохранения секрета."""
        service_name = args.service or config.get_config_value("Secrets", "service_name", "")
        sm = SecretManager(service_name)

        if sm.save_secret(args.key, args.value):
            print(f"[OK] Секрет '{args.key}' успешно сохранен в системном хранилище.")
        else:
            print(f"[ERROR] Не удалось сохранить секрет '{args.key}'. Проверьте доступность keyring.")
            sys.exit(1)

    def handle_delete(self, args: argparse.Namespace):
        """Обработчик команды удаления секрета."""
        service_name = args.service or config.get_config_value("Secrets", "service_name", "")
        sm = SecretManager(service_name)

        if sm.delete_secret(args.key):
            print(f"[OK] Секрет '{args.key}' успешно удален.")
        else:
            print(f"[ERROR] Не удалось удалить секрет '{args.key}' или он не существовал.")
            sys.exit(1)
