import argparse
import sys

from chutils import config
from chutils.secret_manager import SecretManager
from .base import BaseCommand


class SecretsCommand(BaseCommand):
    """
    Управление секретами в системном хранилище (Keyring).
    
    Позволяет безопасно сохранять и удалять API-ключи, пароли и другие
    чувствительные данные, не сохраняя их в открытом виде в коде или конфигах.
    """

    def register(self, subparsers: argparse._SubParsersAction):
        secrets_parser = subparsers.add_parser(
            "secrets",
            help="Управление секретами в системном хранилище",
            description="Команды для работы с системным хранилищем ключей (Windows Credential Manager, Keychain, и т.д.)"
        )
        secrets_parser.set_defaults(handler=self.handle)
        secrets_subparsers = secrets_parser.add_subparsers(dest="subcommand", help="Доступные действия")

        # secrets set <key> <value>
        set_parser = secrets_subparsers.add_parser(
            "set",
            help="Сохранить или обновить секрет",
            description="Сохраняет зашифрованное значение в системное хранилище."
        )
        set_parser.add_argument("key", help="Имя ключа (например, DB_PASSWORD)")
        set_parser.add_argument("value", help="Значение секрета")
        set_parser.add_argument(
            "-s", "--service",
            help="Имя сервиса (service_name). По умолчанию берется из Secrets.service_name в конфиге."
        )
        set_parser.set_defaults(handler=self.handle_set)

        # secrets delete <key>
        delete_parser = secrets_subparsers.add_parser(
            "delete",
            help="Удалить секрет из хранилища",
            description="Навсегда удаляет указанный ключ из системного хранилища."
        )
        delete_parser.add_argument("key", help="Имя ключа для удаления")
        delete_parser.add_argument(
            "-s", "--service",
            help="Имя сервиса (service_name). Должно совпадать с тем, что использовалось при сохранении."
        )
        delete_parser.set_defaults(handler=self.handle_delete)

    def handle(self, args: argparse.Namespace):
        """Вызывается, если подкоманда не указана."""
        print("Используйте 'chutils secrets --help' для просмотра доступных подкоманд.")

    def handle_set(self, args: argparse.Namespace):
        """Обработчик команды сохранения секрета."""
        service_name = args.service or config.get_config_value("Secrets", "service_name", "")
        sm = SecretManager(service_name)

        if sm.save_secret(args.key, args.value):
            self.console.print(
                f"[bold green] [OK] [/bold green] Секрет '{args.key}' успешно сохранен в системном хранилище.")
        else:
            self.console.print(
                f"[bold red] [ERROR] [/bold red] Не удалось сохранить секрет '{args.key}'."
                f" Проверьте доступность keyring.")
            sys.exit(1)

    def handle_delete(self, args: argparse.Namespace):
        """Обработчик команды удаления секрета."""
        service_name = args.service or config.get_config_value("Secrets", "service_name", "")
        sm = SecretManager(service_name)

        if sm.delete_secret(args.key):
            self.console.print(f"[bold green] [OK] [/bold green] Секрет '{args.key}' успешно удален.")
        else:
            self.console.print(
                f"[bold red] [ERROR] [/bold red] Не удалось удалить секрет '{args.key}' или он не существовал.")
            sys.exit(1)
