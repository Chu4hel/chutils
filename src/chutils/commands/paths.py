import argparse
import json

from chutils import config

from .base import BaseCommand


class ShowPathsCommand(BaseCommand):
    """Отображение путей поиска конфигурации."""

    def register(self, subparsers: argparse._SubParsersAction):
        show_paths_parser = subparsers.add_parser("show-paths", help="Показать пути поиска конфигурации")
        show_paths_parser.add_argument("--json", action="store_true", help="Вывод в формате JSON")
        show_paths_parser.set_defaults(handler=self.handle)

    def handle(self, args: argparse.Namespace):
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
