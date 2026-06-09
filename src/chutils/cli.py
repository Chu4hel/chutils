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
        from chutils.exceptions import ChutilsException, PathTraversalError
        from chutils.cli_utils import get_console
        import logging

        console = get_console(stderr=True)

        try:
            args.handler(args)
        except PathTraversalError as e:
            # Специфичное логирование для PathTraversal
            logger = logging.getLogger("chutils.security")
            logger.error(
                "Попытка Path Traversal! Исходный путь: %s, Базовый путь: %s",
                e.context.get('attempted_path'),
                e.context.get('base_path')
            )

            console.print(f"\n[bold red]ОШИБКА БЕЗОПАСНОСТИ:[/bold red] {e.message}")
            if e.hint:
                console.print(f"[bold yellow]СОВЕТ:[/bold yellow] {e.hint}")
            sys.exit(1)

        except ChutilsException as e:
            console.print(f"\n[bold red]ОШИБКА:[/bold red] {e.message}")
            if e.hint:
                # Если доступен Rich, выводим красиво в панели
                from chutils.env import RICH_AVAILABLE
                if RICH_AVAILABLE:
                    from rich.panel import Panel
                    console.print(Panel(e.hint, title="[bold yellow]Подсказка[/bold yellow]", border_style="yellow"))
                else:
                    console.print(f"[bold yellow]СОВЕТ:[/bold yellow] {e.hint}")
            sys.exit(1)

        except Exception as e:
            console.print(f"\n[bold red]НЕПРЕДВИДЕННАЯ ОШИБКА:[/bold red] {e}")
            sys.exit(1)
    else:
        parser.print_help()

    sys.exit(0)


if __name__ == "__main__":
    main()
