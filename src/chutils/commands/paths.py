import argparse
import json

from chutils import config
from .base import BaseCommand


class ShowPathsCommand(BaseCommand):
    """
    Диагностика путей поиска файлов конфигурации.
    
    Показывает корень проекта, обнаруженные файлы и список маркеров,
    которые библиотека использует для поиска настроек.
    """

    def register(self, subparsers: argparse._SubParsersAction):
        show_paths_parser = subparsers.add_parser(
            "show-paths",
            help="Показать пути поиска конфигурации",
            description="Отображение путей, которые chutils использует для загрузки настроек."
        )
        show_paths_parser.add_argument(
            "--json",
            action="store_true",
            help="Вывод информации в формате JSON для автоматической обработки"
        )
        show_paths_parser.set_defaults(handler=self.handle)

    def handle(self, args: argparse.Namespace):
        """Обработчик команды вывода путей поиска конфигурации."""
        from chutils.config.manager import _cm

        # Инициализируем пути, если еще нет
        if not config.are_paths_initialized():
            config.get_base_dir()

        base_dir = config.get_base_dir()
        main_path, env_path, local_path = config.get_config_paths()

        paths_data = {
            "base_dir": base_dir,
            "main_config": main_path,
            "env_config": env_path,
            "local_config": local_path,
            "search_markers": _cm.CONFIG_MARKERS
        }

        if args.json:
            print(json.dumps(paths_data, indent=4, ensure_ascii=False))
        else:
            from chutils.cli_utils import RICH_AVAILABLE
            import os

            if RICH_AVAILABLE and not os.getenv("CH_NO_RICH"):
                from rich.table import Table

                table = Table(title="Диагностика путей конфигурации", show_header=True, header_style="bold magenta")
                table.add_column("Параметр", style="cyan")
                table.add_column("Значение", style="green")

                table.add_row("Корень проекта", base_dir or "[red]Не найден[/red]")
                table.add_row("Основной конфиг", main_path or "[red]Не найден[/red]")
                table.add_row("Конфиг окружения", env_path or "[red]Не найден[/red]")
                table.add_row("Локальный конфиг", local_path or "[red]Не найден[/red]")

                self.console.print(table)

                self.console.print("\n[bold]Список маркеров для поиска (в порядке приоритета):[/bold]")
                for marker in _cm.CONFIG_MARKERS:
                    self.console.print(f" • [yellow]{marker}[/yellow]")
            else:
                print(f"Корень проекта: {base_dir or 'Не найден'}")
                print(f"Основной конфиг: {main_path or 'Не найден'}")
                print(f"Конфиг окружения: {env_path or 'Не найден'}")
                print(f"Локальный конфиг: {local_path or 'Не найден'}")
                print("\nСписок маркеров для поиска (в порядке приоритета):")
                for marker in _cm.CONFIG_MARKERS:
                    print(f" - {marker}")
