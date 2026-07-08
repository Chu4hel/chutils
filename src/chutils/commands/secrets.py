from __future__ import annotations

import argparse
from typing import Any

from chutils import config
from chutils.secret_manager import SecretManager
from .base import BaseCommand


class SecretsCommand(BaseCommand):
    """
    Управление секретами в системном хранилище (Keyring).

    Позволяет безопасно сохранять и удалять API-ключи, пароли и другие
    чувствительные данные, не сохраняя их в открытом виде в коде или конфигах.
    """

    def register(self, subparsers: argparse._SubParsersAction[Any]) -> None:
        from chutils.secret_manager.providers import KEYRING_AVAILABLE

        help_text = (
            "Управление секретами в системном хранилище"
            if KEYRING_AVAILABLE
            else argparse.SUPPRESS
        )

        secrets_parser = subparsers.add_parser(
            "secrets",
            help=help_text,
            description="Команды для работы с системным хранилищем ключей (Windows Credential Manager, Keychain, и т.д.)",
        )
        secrets_parser.set_defaults(handler=self.handle)
        secrets_subparsers = secrets_parser.add_subparsers(
            dest="subcommand", help="Доступные действия"
        )

        # secrets set <key> <value>
        set_parser = secrets_subparsers.add_parser(
            "set",
            help="Сохранить или обновить секрет",
            description="Сохраняет зашифрованное значение в системное хранилище.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""Примеры использования:
  chutils secrets set DB_PASSWORD "mypassword"
  chutils secrets set STRIPE_KEY "sk_test_..." --service my_app
""",
        )
        set_parser.add_argument("key", help="Имя ключа (например, DB_PASSWORD)")
        set_parser.add_argument("value", help="Значение секрета")
        set_parser.add_argument(
            "-s",
            "--service",
            help="Имя сервиса (service_name). По умолчанию берется из Secrets.service_name в конфиге.",
        )
        set_parser.set_defaults(handler=self.handle_set)

        # secrets delete <key>
        delete_parser = secrets_subparsers.add_parser(
            "delete",
            help="Удалить секрет из хранилища",
            description="Навсегда удаляет указанный ключ из системного хранилища.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""Примеры использования:
  chutils secrets delete DB_PASSWORD
  chutils secrets delete STRIPE_KEY --service my_app
""",
        )
        delete_parser.add_argument("key", help="Имя ключа для удаления")
        delete_parser.add_argument(
            "-s",
            "--service",
            help="Имя сервиса (service_name). Должно совпадать с тем, что использовалось при сохранении.",
        )
        delete_parser.set_defaults(handler=self.handle_delete)

        # secrets get <key>
        get_parser = secrets_subparsers.add_parser(
            "get",
            help="Получить секрет из хранилища",
            description="Получает значение указанного ключа из системного хранилища.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""Примеры использования:
  chutils secrets get DB_PASSWORD
  chutils secrets get STRIPE_KEY --service my_app --fallback "default_val"
  chutils secrets get STRIPE_KEY --required
""",
        )
        get_parser.add_argument("key", help="Имя ключа для получения")
        get_parser.add_argument(
            "-s",
            "--service",
            help="Имя сервиса (service_name). По умолчанию берется из Secrets.service_name в конфиге.",
        )
        get_parser.add_argument(
            "--fallback", help="Значение по умолчанию, если секрет не найден."
        )
        get_parser.add_argument(
            "--required",
            action="store_true",
            help="Требовать наличие секрета (вызовет ошибку, если не найден).",
        )
        get_parser.set_defaults(handler=self.handle_get)

    def handle(self, args: argparse.Namespace) -> None:
        """Вызывается, если подкоманда не указана."""
        from chutils.secret_manager.providers import KEYRING_AVAILABLE

        if not KEYRING_AVAILABLE:
            from ..exceptions import CommandError

            raise CommandError(
                "Missing optional dependency: please install chutils[keyring] to use this command."
            )
        print("Используйте 'chutils secrets --help' для просмотра доступных подкоманд.")

    def handle_set(self, args: argparse.Namespace) -> None:
        """Обработчик команды сохранения секрета."""
        from ..exceptions import CommandError, SecretError
        from chutils.secret_manager.providers import KEYRING_AVAILABLE

        if not KEYRING_AVAILABLE:
            raise CommandError(
                "Missing optional dependency: please install chutils[keyring] to use this command."
            )
        service_name = args.service or config.get_config_value(
            "Secrets", "service_name", ""
        )

        try:
            sm = SecretManager(service_name)
            if sm.save_secret(args.key, args.value):
                self.console.print(
                    f"[bold green] [OK] [/bold green] Секрет '{args.key}' успешно сохранен в системном хранилище."
                )
            else:
                raise CommandError(
                    f"Не удалось сохранить секрет '{args.key}'.",
                    hint="Убедитесь, что системное хранилище (keyring) доступно и не заблокировано.",
                )
        except SecretError as e:
            raise CommandError(
                f"Ошибка менеджера секретов: {e.message}", hint=e.hint
            ) from e

    def handle_delete(self, args: argparse.Namespace) -> None:
        """Обработчик команды удаления секрета."""
        from ..exceptions import CommandError, SecretError
        from chutils.secret_manager.providers import KEYRING_AVAILABLE

        if not KEYRING_AVAILABLE:
            raise CommandError(
                "Missing optional dependency: please install chutils[keyring] to use this command."
            )
        service_name = args.service or config.get_config_value(
            "Secrets", "service_name", ""
        )

        try:
            sm = SecretManager(service_name)
            if sm.delete_secret(args.key):
                self.console.print(
                    f"[bold green] [OK] [/bold green] Секрет '{args.key}' успешно удален."
                )
            else:
                raise CommandError(
                    f"Не удалось удалить секрет '{args.key}' или он не существовал.",
                    hint="Проверьте правильность ключа и имени сервиса.",
                )
        except SecretError as e:
            raise CommandError(
                f"Ошибка менеджера секретов: {e.message}", hint=e.hint
            ) from e

    def handle_get(self, args: argparse.Namespace) -> None:
        """Обработчик команды получения секрета."""
        from ..exceptions import CommandError, SecretError
        from chutils.secret_manager.providers import KEYRING_AVAILABLE

        if not KEYRING_AVAILABLE:
            raise CommandError(
                "Missing optional dependency: please install chutils[keyring] to use this command."
            )
        service_name = args.service or config.get_config_value(
            "Secrets", "service_name", ""
        )

        try:
            sm = SecretManager(service_name)
            val = sm.get_secret(
                args.key, fallback=args.fallback, required=args.required
            )
            if val is not None:
                print(val)
        except SecretError as e:
            raise CommandError(
                f"Ошибка менеджера секретов: {e.message}", hint=e.hint
            ) from e
