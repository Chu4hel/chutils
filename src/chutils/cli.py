import argparse
import sys

from chutils.commands import get_commands


def main():
    """Точка входа в CLI."""
    parser = argparse.ArgumentParser(
        prog="chutils",
        description="""
Набор утилит chutils для командной строки.
Помогает инициализировать проекты, управлять секретами и проверять конфигурацию.
""",
        epilog="""
Примеры использования:
  chutils init -y
  chutils secrets set API_KEY "value"
  chutils validate --model myapp.config:Settings
  chutils show-paths --json
""",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subparsers = parser.add_subparsers(
        title="Доступные команды",
        dest="command", 
        metavar="COMMAND",
        help="Используйте 'chutils COMMAND --help' для получения справки по конкретной команде"
    )

    # Регистрируем все доступные команды
    for cmd_class in get_commands():
        cmd_instance = cmd_class()
        cmd_instance.register(subparsers)

    # Если аргументы не переданы, выводим help
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)

    args = parser.parse_args()

    # Диспетчеризация выполнения
    if hasattr(args, 'handler'):
        try:
            args.handler(args)
        except Exception as e:
            print(f"[ERROR] Ошибка при выполнении команды: {e}")
            sys.exit(1)
    else:
        parser.print_help()

    sys.exit(0)


if __name__ == "__main__":
    main()
