from __future__ import annotations

import argparse
import inspect
import json
from pathlib import Path
from typing import Any

import chutils
from .base import BaseCommand


class DevCommand(BaseCommand):
    """
    Команды для разработки и интеграции с AI.

    Позволяет генерировать контекстные данные о библиотеке для LLM.
    """

    def register(self, subparsers: argparse._SubParsersAction[Any]) -> None:
        dev_parser = subparsers.add_parser(
            "dev",
            help="Инструменты разработчика и AI-контекст",
            description="Команды для генерации документации и контекста для LLM/AI агентов.",
        )
        dev_parser.set_defaults(handler=self.handle)
        dev_subparsers = dev_parser.add_subparsers(
            dest="subcommand", help="Доступные действия"
        )

        # dev generate-context
        gen_parser = dev_subparsers.add_parser(
            "generate-context",
            help="Сгенерировать карту публичного API (экспорты)",
            description="Сканирует chutils и создает отчет о доступных функциях, классах и декораторах.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""Примеры использования:
  chutils dev generate-context -o api_map.md
  chutils dev generate-context --tree -o project_index.json
  chutils dev generate-context -f json --no-weights
""",
        )
        gen_parser.add_argument(
            "-f",
            "--format",
            choices=["markdown", "json"],
            default="markdown",
            help="Формат выходных данных (по умолчанию: markdown)",
        )
        gen_parser.add_argument(
            "-o",
            "--output",
            help="Путь к файлу для сохранения (если не указан, выводит в консоль)",
        )
        gen_parser.add_argument(
            "--tree",
            action="store_true",
            help="Генерировать иерархический семантический индекс (JSON дерево)",
        )
        gen_parser.add_argument(
            "--no-weights",
            action="store_true",
            help="Не включать веса зависимостей в графе (только для --tree)",
        )
        gen_parser.add_argument(
            "--include-examples",
            action="store_true",
            help="Включить few-shot примеры (из docs/ai_examples/) в итоговый отчет",
        )
        gen_parser.add_argument(
            "--project",
            nargs="?",
            const=".",
            default=None,
            help="Путь к целевому проекту для сканирования (если не указан, сканируется сама библиотека chutils)",
        )
        gen_parser.set_defaults(handler=self.handle_generate_context)

        # dev ai-lint
        lint_parser = dev_subparsers.add_parser(
            "ai-lint",
            help="Проверить AI-готовность кодовой базы",
            description="Проверяет наличие манифестов ИИ (antigravity.md, agents.md, gemini.md), качество docstrings/type hints и отсутствие секретов.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""Примеры использования:
  chutils dev ai-lint
  chutils dev ai-lint --strict
  chutils dev ai-lint --ignore "temp/,build/"
""",
        )
        lint_parser.add_argument(
            "--strict",
            action="store_true",
            default=None,
            help="Строгий режим: считать предупреждения ошибками и завершаться с ошибкой.",
        )
        lint_parser.add_argument(
            "--soft-mode",
            action="store_true",
            default=None,
            help="Мягкий режим: выводить проблемы, но возвращать успешный статус (0).",
        )
        lint_parser.add_argument(
            "--ignore", help="Список исключаемых путей (через запятую)."
        )
        lint_parser.add_argument(
            "--rules",
            help="Список запускаемых правил через запятую (по умолчанию все).",
        )
        lint_parser.add_argument(
            "--custom-rules-path", help="Путь к файлу с пользовательскими правилами."
        )
        lint_parser.set_defaults(handler=self.handle_ai_lint)

        # dev chat-context
        chat_parser = dev_subparsers.add_parser(
            "chat-context",
            help="Сгенерировать контекстный срез для ИИ-ассистента",
            description="Создает компактный Markdown-срез API, docstrings и examples для ИИ.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""Примеры использования:
  chutils dev chat-context -m logger,secret_manager
  chutils dev chat-context -t "logging and secrets" -l internal -o context.md
  chutils dev chat-context (интерактивный режим)
""",
        )
        chat_parser.add_argument(
            "-m",
            "--modules",
            help="Список модулей через запятую (например: logger,config).",
        )
        chat_parser.add_argument(
            "-t", "--task", help="Описание задачи или темы для автоподбора контекста."
        )
        chat_parser.add_argument(
            "-l",
            "--layer",
            choices=["public", "internal", "infrastructure", "private", "all"],
            default="public",
            help="Фильтр по слоям абстракции (по умолчанию: public)",
        )
        chat_parser.add_argument(
            "-o", "--output", help="Путь к файлу для сохранения результата."
        )
        chat_parser.set_defaults(handler=self.handle_chat_context)

        # dev scaffold
        scaffold_parser = dev_subparsers.add_parser(
            "scaffold",
            help="Инициализировать новый модуль Чистой Архитектуры",
            description="Создает структуру каталогов и базовые классы/интерфейсы Чистой Архитектуры.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""Примеры использования:
  chutils dev scaffold my_module
  chutils dev scaffold my_module -o ./src/my_module -f
""",
        )
        scaffold_parser.add_argument(
            "module_name",
            help="Имя создаваемого модуля (валидный Python-идентификатор)",
        )
        scaffold_parser.add_argument(
            "-o",
            "--output-dir",
            help="Базовый путь для создания каталога модуля (по умолчанию: ./[module_name])",
        )
        scaffold_parser.add_argument(
            "-f",
            "--force",
            action="store_true",
            help="Принудительно перезаписать файлы, если целевая директория уже существует",
        )
        scaffold_parser.set_defaults(handler=self.handle_scaffold)

    def handle(self, args: argparse.Namespace) -> None:
        """Вызывается, если подкоманда не указана."""
        self.console.print(
            "Используйте 'chutils dev --help' для просмотра доступных подкоманд."
        )

    def _collect_symbols_recursive(
            self, node: Any, current_prefix: str = ""
    ) -> list[dict[str, Any]]:
        symbols_data = []
        module_name = current_prefix + node.name if current_prefix else node.name

        for sym in node.symbols:
            if sym.layer != "private" and not sym.name.startswith("_"):
                symbols_data.append(
                    {
                        "name": f"{module_name}.{sym.name}",
                        "type": sym.type,
                        "signature": sym.signature or "",
                        "summary": sym.summary,
                        "full_doc": sym.docstring or "",
                    }
                )

        for child in node.children:
            prefix = f"{module_name}."
            symbols_data.extend(self._collect_symbols_recursive(child, prefix))

        return symbols_data

    def handle_generate_context(self, args: argparse.Namespace) -> None:
        """Обработчик генерации контекста."""
        # Используем stderr для статусных сообщений, чтобы не портить stdout (особенно для JSON)
        self.err_console.print(
            "[bold yellow]Генерация контекста API...[/bold yellow]", style="yellow"
        )

        if args.tree:
            self._handle_tree_index(args)
            return

        api_data: list[dict[str, Any]] = []
        examples = []
        project_name = "chutils"

        if args.project:
            # Сканируем внешний проект через статический AST-анализ
            project_path = Path(args.project).resolve()
            project_name = project_path.name
            try:
                from chutils.dev.ast_indexer import Indexer

                indexer = Indexer(str(project_path))
                index = indexer.index(include_examples=bool(args.include_examples))

                api_data = self._collect_symbols_recursive(index.root)
                examples = index.examples
            except Exception as e:
                self.console.print(
                    f"[bold red]Ошибка при AST-анализе проекта {project_path}: {e}[/bold red]"
                )
                raise SystemExit(1)
        else:
            # Получаем список всех публичных атрибутов chutils
            public_attrs = [attr for attr in dir(chutils) if not attr.startswith("_")]

            for attr_name in public_attrs:
                try:
                    obj = getattr(chutils, attr_name)
                    obj_type = "module"
                    signature = ""
                    doc = inspect.getdoc(obj) or ""

                    # Очистка мусорной документации для констант примитивных типов
                    if (
                            not inspect.isclass(obj)
                            and not inspect.isfunction(obj)
                            and not inspect.ismodule(obj)
                    ):
                        if isinstance(obj, (bool, int, float, str, type(None))):
                            # Если doc совпадает с docstring типа, значит это автогенерированный мусор
                            if doc == inspect.getdoc(type(obj)):
                                doc = ""

                    summary = doc.split("\n")[0] if doc else ""

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

                    import re

                    signature = re.sub(r" at 0x[0-9a-fA-F]+", "", signature)

                    api_data.append(
                        {
                            "name": attr_name,
                            "type": obj_type,
                            "signature": signature,
                            "summary": summary,
                            "full_doc": doc,
                        }
                    )
                except Exception as e:
                    self.console.print(
                        f"[dim red]Ошибка при анализе {attr_name}: {e}[/dim red]"
                    )

            if args.include_examples:
                try:
                    from chutils.dev.ast_indexer import Indexer

                    pkg_path = Path(chutils.__file__).parent
                    indexer = Indexer(str(pkg_path))
                    examples = indexer._collect_examples()
                except Exception as e:
                    self.console.print(
                        f"[dim red]Предупреждение: не удалось загрузить few-shot примеры: {e}[/dim red]"
                    )

        # Сортировка по имени
        api_data.sort(key=lambda x: x["name"])

        output_content = ""
        if args.format == "json":
            if args.include_examples:
                output_data = {
                    "api": api_data,
                    "examples": [
                        {
                            "name": ex.name,
                            "description": ex.description,
                            "good_pattern": ex.good_pattern,
                            "bad_pattern": ex.bad_pattern,
                        }
                        for ex in examples
                    ],
                }
                output_content = json.dumps(output_data, indent=2, ensure_ascii=False)
            else:
                output_content = json.dumps(api_data, indent=2, ensure_ascii=False)
        else:
            # Markdown
            output_content = f"# Public API Map: {project_name}\n\n"
            output_content += "| Name | Type | Signature | Description |\n"
            output_content += "| :--- | :--- | :--- | :--- |\n"
            for item in api_data:
                sig = f"`{item['signature']}`" if item["signature"] else ""
                output_content += f"| `{item['name']}` | {item['type']} | {sig} | {item['summary']} |\n"

            if args.include_examples and examples:
                output_content += "\n## Few-Shot Примеры (Образцы кода)\n"
                for ex in examples:
                    output_content += f"\n### Пример: {ex.name}\n"
                    if ex.description:
                        output_content += f"\n{ex.description}\n"
                    if ex.good_pattern:
                        output_content += f"\n#### Как надо (good_pattern.py)\n```python\n{ex.good_pattern}\n```\n"
                    if ex.bad_pattern:
                        output_content += f"\n#### Как не надо (bad_pattern.py)\n```python\n{ex.bad_pattern}\n```\n"

        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(output_content)
            self.console.print(
                f"[bold green] [OK] [/bold green] Контекст успешно сохранен в: [cyan]{args.output}[/cyan]"
            )
        else:
            if args.format == "json":
                # В stdout выводим чистый JSON для парсинга ИИ
                print(output_content)
            else:
                self.console.print("\n" + output_content)

    def _handle_tree_index(self, args: argparse.Namespace) -> None:
        """Генерация иерархического индекса (Phase 5)."""
        from chutils.exceptions import OptionalDependencyError
        from chutils.env import has_pydantic

        if not has_pydantic():
            raise OptionalDependencyError(
                "Pydantic is required for generating hierarchical project index. "
                "Install it with 'pip install chutils[pydantic]' or 'poetry add pydantic'.",
                dependency="pydantic",
            )

        from chutils.dev.ast_indexer import Indexer

        try:
            if args.project:
                project_path = Path(args.project).resolve()
            else:
                project_path = Path(chutils.__file__).parent

            indexer = Indexer(str(project_path))
            index = indexer.index(include_examples=bool(args.include_examples))

            # Если указано --no-weights, обнуляем веса в графе
            if args.no_weights:
                for edge in index.dependency_graph:
                    edge.weight = 1

            # Семантический индекс всегда в JSON
            output_content = index.model_dump_json(indent=2)

            if args.output:
                with open(args.output, "w", encoding="utf-8") as f:
                    f.write(output_content)
                self.console.print(
                    f"[bold green] [OK] [/bold green] Иерархический индекс успешно сохранен в: [cyan]{args.output}[/cyan]"
                )
            else:
                # В stdout выводим чистый JSON для парсинга ИИ
                print(output_content)

        except Exception as e:
            self.console.print(
                f"[bold red]Ошибка при генерации индекса:[/bold red] {e}"
            )
            raise SystemExit(1)

    def handle_ai_lint(self, args: argparse.Namespace) -> None:
        """Обработчик проверки AI-готовности кодовой базы."""
        cli_args: dict[str, Any] = {}
        if args.strict is not None:
            cli_args["strict"] = args.strict
        if args.soft_mode is not None:
            cli_args["soft_mode"] = args.soft_mode
        if args.ignore:
            cli_args["ignore"] = [
                i.strip() for i in args.ignore.split(",") if i.strip()
            ]
        if args.rules:
            cli_args["rules"] = [r.strip() for r in args.rules.split(",") if r.strip()]
        if args.custom_rules_path:
            cli_args["custom_rules_path"] = args.custom_rules_path

        # Ленивый импорт конфигурации и движка
        from chutils.config.dev import load_ai_lint_config
        from chutils.dev.ai_lint import LinterEngine

        try:
            config = load_ai_lint_config(cli_args=cli_args)
            engine = LinterEngine(config)

            self.err_console.print(
                "[bold yellow]Запуск аудита AI-готовности кодовой базы...[/bold yellow]"
            )
            results = engine.run()
            success = engine.print_results(results)

            if not success:
                raise SystemExit(1)
        except Exception as e:
            self.console.print(
                f"[bold red]Ошибка при выполнении ai-lint:[/bold red] {e}"
            )
            raise SystemExit(1)

    def handle_chat_context(self, args: argparse.Namespace) -> None:
        """Обработчик интерактивной сборки контекста."""
        from pathlib import Path
        from chutils.dev.chat_context import collect_context_slice, run_interactive_menu

        modules_list = None
        if args.modules:
            modules_list = [m.strip() for m in args.modules.split(",") if m.strip()]

        project_path = Path(".").resolve()

        # Если не указаны ни модули, ни задача, запускаем интерактивный режим
        if not modules_list and not args.task:
            modules_list = run_interactive_menu(project_path)
            if not modules_list:
                return

        self.err_console.print(
            "[bold yellow]Сборка контекстного среза...[/bold yellow]"
        )

        try:
            markdown_content = collect_context_slice(
                project_path=project_path,
                modules=modules_list,
                task=args.task,
                layer=args.layer,
            )

            if args.output:
                output_path = Path(args.output).resolve()
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text(markdown_content, encoding="utf-8")
                self.console.print(
                    f"[bold green] [OK] [/bold green] Контекстный срез успешно сохранен в: [cyan]{args.output}[/cyan]"
                )
            else:
                # В stdout выводим сгенерированный Markdown
                print(markdown_content)

        except Exception as e:
            self.console.print(
                f"[bold red]Ошибка при генерации контекста:[/bold red] {e}"
            )
            raise SystemExit(1)

    def handle_scaffold(self, args: argparse.Namespace) -> None:
        """Обработчик генерации структуры модуля."""
        self.err_console.print(
            f"[bold yellow]Инициализация модуля Чистой Архитектуры '{args.module_name}'...[/bold yellow]"
        )
        from chutils.dev.scaffold import Scaffolder

        try:
            scaffolder = Scaffolder(
                module_name=args.module_name,
                output_dir=args.output_dir,
                force=args.force,
            )
            scaffolder.scaffold()
            self.console.print(
                f"[bold green] [OK] [/bold green] Модуль '{args.module_name}' успешно инициализирован."
            )
        except Exception as e:
            self.console.print(
                f"[bold red]Ошибка инициализации:[/bold red] {e}"
            )
            raise SystemExit(1)
