import argparse

from chutils import config
from chutils.config.diagnostics import format_trace
from chutils.config.manager import _cm

from .base import BaseCommand


class ConfigCommand(BaseCommand):
    """
    Команды для работы с конфигурацией и её диагностики.
    """

    def register(self, subparsers: argparse._SubParsersAction):
        config_parser = subparsers.add_parser(
            "config",
            help="Управление и диагностика конфигурации",
            description="Группа команд для работы с настройками приложения, их проверки и отладки."
        )
        config_parser.set_defaults(handler=self.handle)
        config_subparsers = config_parser.add_subparsers(dest="subcommand", help="Доступные действия")

        # config debug
        debug_parser = config_subparsers.add_parser(
            "debug",
            help="Интерактивный отладчик конфигурации (Trace)",
            description="Показывает итоговую конфигурацию и историю её изменения из разных источников."
        )
        debug_parser.add_argument(
            "-f", "--format",
            choices=["tree", "table", "json"],
            default="tree",
            help="Формат вывода данных (по умолчанию: tree)"
        )
        debug_parser.add_argument(
            "--show-secrets",
            action="store_true",
            help="Показывать реальные значения секретов вместо [MASKED]"
        )
        debug_parser.set_defaults(handler=self.handle_debug)

        # config generate-schema
        schema_parser = config_subparsers.add_parser(
            "generate-schema",
            help="Генерация JSON Schema на основе Pydantic модели",
            description="Создает JSON схему для валидации файлов конфигурации в IDE или AI-агентах."
        )
        schema_parser.add_argument(
            "--model",
            required=True,
            help="Путь к Pydantic модели в формате 'module.path:ClassName'"
        )
        schema_parser.add_argument(
            "-o", "--output",
            help="Путь к файлу для сохранения схемы (например, config.schema.json)"
        )
        schema_parser.add_argument(
            "--stdout",
            action="store_true",
            help="Вывести схему в консоль (игнорируется, если не указан --output)"
        )
        schema_parser.set_defaults(handler=self.handle_generate_schema)

    def handle(self, args: argparse.Namespace):
        """Вызывается, если подкоманда не указана."""
        print("Используйте 'chutils config --help' для просмотра доступных подкоманд.")

    def handle_debug(self, args: argparse.Namespace):
        """Обработчик команды отладки конфигурации."""
        # 1. Включаем трассировку
        _cm.tracing_enabled = True

        # 2. Сбрасываем кэш, чтобы гарантировать полную перегрузку и сбор всех источников
        _cm.clear_cache()

        # 3. Принудительно загружаем конфигурацию
        config.get_config()

        # 4. Получаем данные трассировки
        trace_data = _cm.get_trace()

        if not trace_data:
            self.console.print("[yellow]Данные конфигурации не найдены.[/yellow]")
            return

        # 5. Форматируем и выводим
        output = format_trace(
            trace_data,
            format_type=args.format,
            show_secrets=args.show_secrets
        )

        # Для JSON выводим напрямую, для остальных используем console.print
        if args.format == 'json':
            print(output)
        else:
            # Отключаем markup, так как в текстовом режиме [section] воспринимается как тег и удаляется
            self.console.print(output, markup=False)

    def handle_generate_schema(self, args: argparse.Namespace):
        """Обработчик команды генерации JSON Schema."""
        from chutils.config import export_schema

        try:
            schema_json = export_schema(
                model=args.model,
                output_path=args.output
            )

            if args.output:
                if not args.stdout:
                    self.console.print(f"[green]JSON Schema успешно сохранена в: [bold]{args.output}[/bold][/green]")
                else:
                    # Если указан и --output и --stdout, выводим и туда и туда
                    print(schema_json)
            else:
                # Если выходной файл не указан, всегда выводим в stdout
                print(schema_json)

        except Exception as e:
            self.console.print(f"[red]Ошибка при генерации схемы:[/red] {e}")
            raise SystemExit(1)
