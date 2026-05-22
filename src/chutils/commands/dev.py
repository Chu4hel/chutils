import argparse

from .base import BaseCommand


class DevCommand(BaseCommand):
    """
    Команды для разработки и интеграции с AI.
    
    Позволяет генерировать контекстные данные о библиотеке для LLM.
    """

    def register(self, subparsers: argparse._SubParsersAction):
        dev_parser = subparsers.add_parser(
            "dev",
            help="Инструменты разработчика и AI-контекст",
            description="Команды для генерации документации и контекста для LLM/AI агентов."
        )
        dev_parser.set_defaults(handler=self.handle)
        dev_subparsers = dev_parser.add_subparsers(dest="subcommand", help="Доступные действия")

        # dev generate-context
        gen_parser = dev_subparsers.add_parser(
            "generate-context",
            help="Сгенерировать карту публичного API (экспорты)",
            description="Сканирует chutils и создает отчет о доступных функциях, классах и декораторах."
        )
        gen_parser.add_argument(
            "-f", "--format",
            choices=["markdown", "json"],
            default="markdown",
            help="Формат выходных данных (по умолчанию: markdown)"
        )
        gen_parser.add_argument(
            "-o", "--output",
            help="Путь к файлу для сохранения (если не указан, выводит в консоль)"
        )
        gen_parser.set_defaults(handler=self.handle_generate_context)

    def handle(self, args: argparse.Namespace):
        """Вызывается, если подкоманда не указана."""
        self.console.print("Используйте 'chutils dev --help' для просмотра доступных подкоманд.")

    def handle_generate_context(self, args: argparse.Namespace):
        """Обработчик генерации контекста."""
        import inspect
        import json
        import sys
        import chutils

        # Используем stderr для статусных сообщений, чтобы не портить stdout (особенно для JSON)
        err_console = self.console
        if hasattr(self.console, "file") and self.console.file != sys.stderr:
            from rich.console import Console
            err_console = Console(stderr=True)

        err_console.print("[bold yellow]Генерация контекста API...[/bold yellow]", style="yellow")

        api_data = []
        # Получаем список всех публичных атрибутов chutils
        public_attrs = [attr for attr in dir(chutils) if not attr.startswith('_')]

        for attr_name in public_attrs:
            try:
                obj = getattr(chutils, attr_name)
                obj_type = "module"
                signature = ""
                doc = inspect.getdoc(obj) or ""
                summary = doc.split('\n')[0] if doc else ""

                if inspect.isfunction(obj):
                    obj_type = "function"
                    try:
                        signature = str(inspect.signature(obj))
                    except ValueError:
                        signature = "(...)"
                elif inspect.isclass(obj):
                    obj_type = "class"
                    try:
                        signature = str(inspect.signature(obj.__init__))
                        if signature == "(self, /)":
                            signature = "()"
                    except (ValueError, TypeError, AttributeError):
                        signature = "(...)"
                elif inspect.ismodule(obj):
                    obj_type = "module"
                else:
                    obj_type = "constant"

                api_data.append({
                    "name": attr_name,
                    "type": obj_type,
                    "signature": signature,
                    "summary": summary,
                    "full_doc": doc
                })
            except Exception as e:
                self.console.print(f"[dim red]Ошибка при анализе {attr_name}: {e}[/dim red]")

        # Сортировка по имени
        api_data.sort(key=lambda x: x["name"])

        output_content = ""
        if args.format == "json":
            output_content = json.dumps(api_data, indent=2, ensure_ascii=False)
        else:
            # Markdown
            output_content = "# Public API Map: chutils\n\n"
            output_content += "| Name | Type | Signature | Description |\n"
            output_content += "| :--- | :--- | :--- | :--- |\n"
            for item in api_data:
                sig = f"`{item['signature']}`" if item['signature'] else ""
                output_content += f"| `{item['name']}` | {item['type']} | {sig} | {item['summary']} |\n"

        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(output_content)
            self.console.print(
                f"[bold green] [OK] [/bold green] Контекст успешно сохранен в: [cyan]{args.output}[/cyan]")
        else:
            self.console.print("\n" + output_content)
