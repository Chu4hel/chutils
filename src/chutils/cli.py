from __future__ import annotations

import argparse
import sys

from chutils.commands import get_commands


def main() -> None:
    """Точка входа в CLI."""
    from chutils.secret_manager.providers import KEYRING_AVAILABLE

    description = """
Набор утилит chutils для командной строки.
Помогает инициализировать проекты, управлять секретами и проверять конфигурацию.
"""
    if not KEYRING_AVAILABLE:
        description += "\nДля команд управления секретами установите опциональную зависимость: pip install chutils[keyring]"

    parser = argparse.ArgumentParser(
        prog="chutils",
        description=description,
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
        from chutils.env import RICH_AVAILABLE
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

            if RICH_AVAILABLE:
                from rich.text import Text
                console.print()
                console.print(Text("ОШИБКА БЕЗОПАСНОСТИ: ", style="bold red") + Text(e.message))
                if e.hint:
                    console.print(Text("СОВЕТ: ", style="bold yellow") + Text(e.hint))
            else:
                console.print(f"\nОШИБКА БЕЗОПАСНОСТИ: {e.message}", markup=False)
                if e.hint:
                    console.print(f"СОВЕТ: {e.hint}", markup=False)
            sys.exit(1)

        except ChutilsException as e:
            if RICH_AVAILABLE:
                from rich.text import Text
                from rich.panel import Panel
                # Выводим префикс стилизованно, а сообщение как чистый текст (защита от markup)
                console.print()
                console.print(Text("ОШИБКА: ", style="bold red") + Text(e.message))

                if e.hint:
                    # Внутри панели используем Text для защиты от markup
                    console.print(
                        Panel(Text(e.hint), title="[bold yellow]Подсказка[/bold yellow]", border_style="yellow"))
            else:
                console.print(f"\nОШИБКА: {e.message}", markup=False)
                if e.hint:
                    console.print(f"СОВЕТ: {e.hint}", markup=False)
            sys.exit(1)

        except Exception as e:
            if RICH_AVAILABLE:
                from rich.text import Text
                console.print()
                console.print(Text("НЕПРЕДВИДЕННАЯ ОШИБКА: ", style="bold red") + Text(str(e)))
            else:
                console.print(f"\nНЕПРЕДВИДЕННАЯ ОШИБКА: {e}", markup=False)
            sys.exit(1)


    else:
        parser.print_help()

    sys.exit(0)


if __name__ == "__main__":
    main()
